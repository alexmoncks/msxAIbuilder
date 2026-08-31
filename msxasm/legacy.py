#!/usr/bin/env python3
"""
minz80asm.py - Minimal Z80 assembler for MSX ROM generation.
v2 - Fixed instruction ordering and encoding.
"""

import re
import struct
import sys
from typing import Dict, List, Tuple, Optional

from msxasm.errors import MontagemError

_LOOKS_LIKE_CODE = re.compile(
    r'^(ld|call|ret|reti|retn|jr|jp|out|in|xor|or|and|cp|add|adc|sub|sbc|inc|dec|'
    r'push|pop|djnz|neg|nop|ex|exx|set|res|bit|rl|rr|rlc|rrc|sla|sra|srl|rla|rra|'
    r'rlca|rrca|ei|di|halt|outi|otir|ini|inir|ldi|ldir|ldd|lddr|cpl|scf|ccf|daa|'
    r'rst|db|dw|ds)\b', re.IGNORECASE)


class Z80Assembler:
    def __init__(self):
        self.org = 0
        self.output = bytearray()
        self.labels: Dict[str, int] = {}
        self.equates: Dict[str, int] = {}
        self.current_address = 0
        self.pass_no = 1
        self.max_passes = 2
        self.include_paths = []
        self.arquivo_base = None
        self.linha_atual = None
        self.linhas_fonte = None

    def assemble(self, source: str) -> bytearray:
        lines = source.split('\n')

        for self.pass_no in range(1, self.max_passes + 1):
            self.output = bytearray()
            self.current_address = 0
            
            i = 0
            while i < len(lines):
                line = lines[i]
                self.linha_atual = i + 1
                stripped = line.strip()
                if not stripped or stripped.startswith(';'):
                    i += 1
                    continue
                
                # Remove comments (but not in strings)
                bp = self._find_comment(stripped)
                if bp >= 0:
                    dropped = stripped[bp+1:].strip()
                    # ';' e COMENTARIO em Z80, nao separador de instrucoes.
                    # Avisa se o texto descartado parece codigo — foi exatamente
                    # assim que 89 linhas do Pong sumiram sem nenhum erro.
                    if self.pass_no == self.max_passes and _LOOKS_LIKE_CODE.match(dropped):
                        print(f"  ASM WARN: texto apos ';' parece INSTRUCAO e foi "
                              f"descartado como comentario -> {dropped!r}\n"
                              f"            (linha: {stripped!r}) "
                              f"use UMA instrucao por linha", file=sys.stderr)
                    stripped = stripped[:bp].strip()
                if not stripped:
                    i += 1
                    continue
                
                # Handle labels
                if ':' in stripped:
                    col_pos = stripped.find(':')
                    label_part = stripped[:col_pos].strip()
                    rest = stripped[col_pos+1:].strip()
                    if self._is_valid_label(label_part):
                        if label_part.upper() not in self.equates:
                            if label_part not in self.labels:
                                self.labels[label_part] = self.current_address
                        stripped = rest if rest else ''
                        if not stripped:
                            i += 1
                            continue
                
                # EQU directive
                eq = re.match(r'(\w+)\s+EQU\s+(.+)', stripped, re.IGNORECASE)
                if eq:
                    # Reavaliar em TODA passagem, nao so na primeira. So assim
                    # dois casos ficam corretos ao mesmo tempo: referencia
                    # adiante a um label (ex.: TAM EQU FIM - INICIO, com FIM
                    # definido depois) resolve na passagem final, quando FIM
                    # ja existe em self.labels; e simbolo que nunca existe
                    # vira MontagemError na passagem final, em vez de gravar 0
                    # em silencio para sempre porque _eval so levanta na
                    # ultima passagem e EQU antes so era avaliado na primeira.
                    self.equates[eq.group(1).upper()] = self._eval(eq.group(2))
                    i += 1
                    continue
                
                # ORG/DW/DB/DS/INCBIN
                d = re.match(r'(ORG|DB|DW|DS|INCBIN)\b(.+)?$', stripped, re.IGNORECASE)
                if d:
                    try:
                        self._directive(d.group(1).upper(), d.group(2))
                    except MontagemError:
                        # Erro real (ex.: simbolo inexistente dentro da
                        # expressao da diretiva) ja vem com linha de origem
                        # de _eval -- propaga direto, sem reembrulhar.
                        raise
                    except Exception as e:
                        # Diretiva malformada (ex.: DB/DW sem operando vira
                        # TypeError cru dentro de _parse_nums) escapava sem
                        # arquivo nem linha, atravessando o "except
                        # MontagemError" da CLI como traceback bruto. Guarda
                        # o repr do erro original na mensagem -- rastro do
                        # que de fato aconteceu, para nao confundir engano de
                        # sintaxe do usuario com bug de implementacao.
                        raise MontagemError(
                            f"diretiva {d.group(1).upper()} mal formada em "
                            f"{stripped!r}: {e!r}",
                            linha=self.linha_atual,
                            arquivo=str(self.arquivo_base) if self.arquivo_base else None,
                        ) from e
                    i += 1
                    continue
                
                # Encode instruction
                try:
                    code = self._encode(stripped)
                    self.output.extend(code)
                    self.current_address += len(code)
                except MontagemError:
                    # Simbolo inexistente na ultima passagem: erro real, nao
                    # instrucao mal-codificada. Propaga direto como
                    # MontagemError, com a linha de origem.
                    raise
                except Exception as e:
                    if self.pass_no == self.max_passes:
                        # No passe final isto NAO e aviso: e uma instrucao que
                        # nao entrou no binario -- por exemplo, mnemonico
                        # desconhecido (_encode levanta ValueError puro para
                        # esse caso). Seguir em frente foi o que produziu ROMs
                        # com buracos silenciosos; virava SystemExit sem
                        # arquivo nem linha. Agora sai como qualquer outra
                        # falha de montagem: MontagemError com arquivo:linha.
                        raise MontagemError(
                            str(e),
                            linha=self.linha_atual,
                            arquivo=str(self.arquivo_base) if self.arquivo_base else None,
                        ) from e
                    self.current_address += self._guess_size(stripped)
                i += 1

        return self.output

    # ------------------------------------------------------------------ helpers
    def _find_comment(self, s: str) -> int:
        q = False
        for i, c in enumerate(s):
            q ^= (c in '"\''); 
            if c == ';' and not q: 
                return i
        return -1

    def _check_jr(self, diff: int, line: str):
        # Salto relativo so alcanca -128..+127. Sem este aviso o deslocamento
        # era truncado em silencio e o programa pulava para o lugar errado.
        if diff < -128 or diff > 127:
            print(f"  ASM ERRO: salto relativo fora de alcance ({diff}) -> {line!r}"
                  f"  use JP em vez de JR", file=sys.stderr)

    def _is_valid_label(self, s: str) -> bool:
        return bool(re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', s))

    def _eval(self, expr: str) -> int:
        if not expr:
            return 0
        # Normalize
        e = expr.strip().upper()
        # Replace labels
        for lbl, val in sorted(self.labels.items(), key=lambda x: -len(x[0])):
            e = re.sub(r'\b' + re.escape(lbl) + r'\b', str(val), e)
        for lbl, val in sorted(self.equates.items(), key=lambda x: -len(x[0])):
            e = re.sub(r'\b' + re.escape(lbl) + r'\b', str(val), e)
        e = e.replace('$', str(self.current_address))
        # Intel hex (both 0xNN and NNNNh)
        e = re.sub(r'0X([0-9A-F]+)', r'0x\1', e)
        e = re.sub(r'(?<![0-9A-F])([0-9A-F]+)H\b', r'0x\1', e)
        # Binary NNb.
        # O lookbehind e OBRIGATORIO: depois da conversao hex acima, '0C00Bh'
        # ja virou '0x0C00B', e '([01]+)B\b' casava com o '00B' final,
        # transformando 0C00Bh em 0x0C0 = 192 -- silenciosamente. Qualquer
        # constante hex terminada em ...0B ou ...1B caia nessa (e '0Bh' virava 0).
        # Exigir que o digito anterior nao seja hex nem o 'x' de '0x' resolve,
        # sem afetar literais binarios de verdade, que sempre comecam depois de
        # um separador (inicio, espaco, virgula, operador).
        e = re.sub(r'(?<![0-9A-Fx])([01]+)B\b', lambda m: str(int(m.group(1), 2)), e)
        try:
            return int(eval(e, {"__builtins__": {}}, {}))
        except Exception:
            # Na passagem 1 referencias adiante ainda nao existem: devolver 0 e
            # correto, a passagem 2 resolve. Na ultima passagem, nao resolver
            # significa que o simbolo nao existe -- e devolver 0 em silencio
            # produz uma ROM que monta e trava.
            if self.pass_no == self.max_passes:
                # Depois do achatamento de INCLUDE (Tarefa 4), self.linha_atual
                # indexa a lista achatada, nao o arquivo original -- por isso
                # mapeamos de volta via linhas_fonte para reportar o
                # arquivo/numero de onde a linha realmente veio (o modulo),
                # em vez de um offset do fonte achatado.
                origem = None
                if self.linhas_fonte and self.linha_atual:
                    idx = self.linha_atual - 1
                    if 0 <= idx < len(self.linhas_fonte):
                        origem = self.linhas_fonte[idx]
                raise MontagemError(
                    f"expressao nao pode ser avaliada: {expr!r} "
                    f"(apos substituicao de simbolos: {e!r})",
                    linha=origem.numero if origem else self.linha_atual,
                    arquivo=origem.arquivo if origem else (
                        str(self.arquivo_base) if self.arquivo_base else None),
                )
            return 0

    def _parse_nums(self, s: str) -> List[int]:
        """Parse comma-separated list of numbers or strings."""
        vals = []
        i = 0
        while i < len(s):
            if s[i] in '"\'':
                q = s[i]; i += 1
                while i < len(s) and s[i] != q:
                    vals.append(ord(s[i])); i += 1
                i += 1
            elif s[i] in ', ':
                i += 1
            else:
                j = i
                while j < len(s) and s[j] not in ',;':
                    j += 1
                vals.append(self._eval(s[i:j]))
                i = j
        return vals

    def _reg8(self, r: str) -> Optional[int]:
        m = {'B':0, 'C':1, 'D':2, 'E':3, 'H':4, 'L':5, '(HL)':6, 'A':7}
        return m.get(r.upper())

    def _reg16(self, r: str) -> Optional[int]:
        m = {'BC':0, 'DE':1, 'HL':2, 'SP':3, 'AF':3}
        return m.get(r.upper())

    def _cc(self, s: str) -> Optional[int]:
        m = {'NZ':0,'Z':1,'NC':2,'C':3,'PO':4,'PE':5,'P':6,'M':7}
        return m.get(s.upper())

    # ------------------------------------------------------------------ directive
    def _directive(self, dir: str, arg: Optional[str]):
        if dir == 'ORG':
            v = self._eval(arg)
            if v > self.current_address and self.current_address > 0:
                self.output.extend([0] * (v - self.current_address))
            self.current_address = v
            if self.org == 0:
                self.org = v
        elif dir == 'DB':
            for b in self._parse_nums(arg):
                self.output.append(b & 0xFF)
                self.current_address += 1
        elif dir == 'DW':
            for w in self._parse_nums(arg):
                self.output.extend([w & 0xFF, (w >> 8) & 0xFF])
                self.current_address += 2
        elif dir == 'DS':
            parts = arg.split(',') if arg else ['0']
            cnt = self._eval(parts[0])
            val = self._eval(parts[1]) if len(parts) > 1 else 0
            self.output.extend([val & 0xFF] * cnt)
            self.current_address += cnt

    # ------------------------------------------------------------------ encode
    def _is_num(self, s: str) -> bool:
        s = s.strip().upper()
        if s.startswith('0X') or s.startswith('0x'):
            return all(c in '0123456789ABCDEFabcdef' for c in s[2:])
        if s.endswith('H'):
            return bool(re.match(r'^[0-9][0-9A-F]*H$', s))
        return s.lstrip('-').isdigit()

    def _encode(self, line: str) -> List[int]:
        u = line.strip()
        # Split by space or comma
        parts = re.split(r'[\s,]+', u)
        op = parts[0].upper() if parts else ''
        args = u[len(op):].strip()
        # Remove leading comma
        if args.startswith(','):
            args = args[1:].strip()
        
        b: List[int] = []

        # ---- NOP / HALT / DI / EI / RET / EXX / DAA / CPL / SCF / CCF / RLCA / RRCA / RLA / RRA
        one = {'NOP': 0x00, 'HALT': 0x76, 'DI': 0xF3, 'EI': 0xFB, 'RET': 0xC9,
               'EXX': 0xD9, 'DAA': 0x27, 'CPL': 0x2F, 'SCF': 0x37, 'CCF': 0x3F,
               'RLCA': 0x07, 'RRCA': 0x0F, 'RLA': 0x17, 'RRA': 0x1F}
        if op in one and not args:
            return [one[op]]

        # ---- RET cc
        if op == 'RET' and args:
            c = self._cc(args)
            if c is not None:
                return [0xC0 | (c << 3)]

        # ---- RST nn
        if op == 'RST':
            v = self._eval(args)
            if v in [0, 8, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38]:
                return [0xC7 | v]
        
        # ---- PUSH / POP (IX, IY)
        if op in ('PUSH', 'POP') and args in ('IX', 'IY'):
            p = 0xDD if args == 'IX' else 0xFD
            return [p, 0xE5 if op == 'PUSH' else 0xE1]
        # ---- PUSH / POP (standard)
        if op in ('PUSH', 'POP'):
            r = self._reg16(args)
            if r is not None:
                base = 0xC5 if op == 'PUSH' else 0xC1
                return [base | (r << 4)]

        # ---- EX DE,HL
        if op == 'EX':
            if args.upper().replace(' ','') == 'DE,HL':
                return [0xEB]
            if args.upper().replace(' ','') == 'AF,AF\'':
                return [0x08]

        # ---- JR d
        if op == 'JR' and args:
            if ',' in args:
                cc_s, target = args.split(',', 1)
                cc_s = cc_s.strip()
                target = target.strip()
                cc = self._cc(cc_s)
                if cc is not None and cc < 4:
                    jr_map = {0: 0x20, 1: 0x28, 2: 0x30, 3: 0x38}
                    v = self._eval(target)
                    if self.pass_no == self.max_passes:
                        diff = v - (self.current_address + 2)
                        self._check_jr(diff, u)
                        return [jr_map[cc], diff & 0xFF]
                    return [jr_map[cc], 0]
            else:
                v = self._eval(args)
                if self.pass_no == self.max_passes:
                    diff = v - (self.current_address + 2)
                    self._check_jr(diff, u)
                    return [0x18, diff & 0xFF]
                return [0x18, 0]
        
        # ---- DJNZ d
        if op == 'DJNZ':
            v = self._eval(args)
            if self.pass_no == self.max_passes:
                diff = v - (self.current_address + 2)
                self._check_jr(diff, u)
                return [0x10, diff & 0xFF]
            return [0x10, 0]
        
        # ---- JP (HL) / JP (IX) / JP (IY)
        if op == 'JP' and args.startswith('('):
            inner = args[1:-1].strip()
            if inner == 'HL':
                return [0xE9]
            elif inner == 'IX':
                return [0xDD, 0xE9]
            elif inner == 'IY':
                return [0xFD, 0xE9]
        
        # ---- JP cc,nn
        if op == 'JP' and ',' in args:
            cc_s, target = args.split(',', 1)
            cc = self._cc(cc_s.strip())
            if cc is not None:
                v = self._eval(target.strip())
                return [0xC2 | (cc << 3), v & 0xFF, (v >> 8) & 0xFF]
        
        # ---- JP nn
        if op == 'JP':
            v = self._eval(args)
            return [0xC3, v & 0xFF, (v >> 8) & 0xFF]
        
        # ---- CALL cc,nn
        if op == 'CALL' and ',' in args:
            cc_s, target = args.split(',', 1)
            cc = self._cc(cc_s.strip())
            if cc is not None:
                v = self._eval(target.strip())
                return [0xC4 | (cc << 3), v & 0xFF, (v >> 8) & 0xFF]
        
        # ---- CALL nn
        if op == 'CALL':
            v = self._eval(args)
            return [0xCD, v & 0xFF, (v >> 8) & 0xFF]
        
        # ---- INC/DEC IX, IY
        if op in ('INC', 'DEC') and args in ('IX', 'IY'):
            p = 0xDD if args == 'IX' else 0xFD
            return [p, 0x23 if op == 'INC' else 0x2B]
        
        # ---- INC/DEC (IX/IY+d)
        m = re.match(r'(INC|DEC)\s*\(\s*(IX|IY)\s*\+\s*(\d+)\s*\)', u, re.IGNORECASE)
        if m:
            op2 = m.group(1).upper()
            r = m.group(2).upper()
            d = int(m.group(3)) & 0xFF
            p = 0xDD if r == 'IX' else 0xFD
            return [p, 0x34 if op2 == 'INC' else 0x35, d]
        
        # ---- INC/DEC BC, DE, HL, SP
        if op in ('INC', 'DEC'):
            r = self._reg16(args)
            if r is not None:
                return [0x03 + (r << 4) if op == 'INC' else 0x0B + (r << 4)]
        
        # ---- INC/DEC r
        if op in ('INC', 'DEC'):
            r = self._reg8(args)
            if r is not None:
                base = 0x04 if op == 'INC' else 0x05
                return [base + (r << 3)]
        
        # ---- LD (HL),r / LD r,(HL) / LD (HL),n / LD A,(BC) etc
        if op == 'LD' and args:
            raw_dst, raw_src = args.split(',', 1)
            dst = raw_dst.strip()
            src = raw_src.strip()
            d_u = dst.upper()
            s_u = src.upper()
            
            # LD r,(HL)
            m1 = re.match(r'\(HL\)', s_u)
            if m1:
                r = self._reg8(d_u)
                if r is not None:
                    return [0x46 | (r << 3)]
            
            # LD (HL),r
            m2 = re.match(r'\(HL\)', d_u)
            if m2:
                r = self._reg8(s_u)
                if r is not None:
                    return [0x70 | r]
            
            # LD (HL),n
            m3 = re.match(r'\(HL\)', d_u)
            if m3:
                v = self._eval(src)
                return [0x36, v & 0xFF]
            
            # LD A,(BC) / LD A,(DE) — must check BEFORE LD A,(nn)!
            if d_u == 'A':
                m_bcde = re.match(r'\((BC|DE)\)', s_u)
                if m_bcde:
                    return [0x0A if m_bcde.group(1) == 'BC' else 0x1A]
            
            # LD (BC),A / LD (DE),A — must check BEFORE LD (nn),A!
            if s_u == 'A':
                m_bcde2 = re.match(r'\((BC|DE)\)', d_u)
                if m_bcde2:
                    return [0x02 if m_bcde2.group(1) == 'BC' else 0x12]
            
            # LD A,(nn)
            if d_u == 'A':
                m6 = re.match(r'\((.+)\)', src)
                if m6:
                    v = self._eval(m6.group(1))
                    return [0x3A, v & 0xFF, (v >> 8) & 0xFF]
            
            # LD (nn),A
            if s_u == 'A':
                m7 = re.match(r'\((.+)\)', dst)
                if m7:
                    v = self._eval(m7.group(1))
                    return [0x32, v & 0xFF, (v >> 8) & 0xFF]
            
            # LD SP,HL
            if d_u == 'SP' and s_u == 'HL':
                return [0xF9]
            
            # LD SP,IX / LD SP,IY
            if d_u == 'SP' and s_u in ('IX', 'IY'):
                return [0xDD if s_u == 'IX' else 0xFD, 0xF9]
            
            # LD rr,(nn) e LD (nn),rr.
            # TEM de vir antes do imediato: senao '(nn)' e avaliado como numero
            # e 'ld hl,(VAR)' vira 'ld hl,VAR' silenciosamente -- carrega o
            # ENDERECO em vez do conteudo. Mesma classe de bug do 0C00Bh.
            if d_u in ('BC', 'DE', 'HL', 'SP'):
                m_ind = re.match(r'^\((.+)\)$', src.strip())
                if m_ind:
                    v = self._eval(m_ind.group(1))
                    if d_u == 'HL':
                        return [0x2A, v & 0xFF, (v >> 8) & 0xFF]
                    ed = {'BC': 0x4B, 'DE': 0x5B, 'SP': 0x7B}[d_u]
                    return [0xED, ed, v & 0xFF, (v >> 8) & 0xFF]
            if s_u in ('BC', 'DE', 'HL', 'SP'):
                m_ind = re.match(r'^\((.+)\)$', dst.strip())
                if m_ind:
                    v = self._eval(m_ind.group(1))
                    if s_u == 'HL':
                        return [0x22, v & 0xFF, (v >> 8) & 0xFF]
                    ed = {'BC': 0x43, 'DE': 0x53, 'SP': 0x73}[s_u]
                    return [0xED, ed, v & 0xFF, (v >> 8) & 0xFF]

            # LD BC/DE/HL/SP,nn
            r16 = self._reg16(d_u)
            if r16 is not None:
                v = self._eval(src)
                return [0x01 | (r16 << 4), v & 0xFF, (v >> 8) & 0xFF]
            
            # LD IX,nn / LD IY,nn
            if d_u in ('IX', 'IY'):
                p = 0xDD if d_u == 'IX' else 0xFD
                v = self._eval(src)
                return [p, 0x21, v & 0xFF, (v >> 8) & 0xFF]
            
            # LD r,r'
            r_dst = self._reg8(d_u)
            r_src = self._reg8(s_u)
            if r_dst is not None and r_src is not None:
                return [0x40 | (r_dst << 3) | r_src]
            
            # LD r,n
            r_dst = self._reg8(d_u)
            if r_dst is not None:
                v = self._eval(src)
                return [0x06 | (r_dst << 3), v & 0xFF]
        
        # ---- ADD A,r / ADD A,n
        if op == 'ADD':
            if args.upper().startswith('A'):
                rest = args[1:].strip().lstrip(',').strip()
                r = self._reg8(rest)
                if r is not None:
                    return [0x80 | r]
                v = self._eval(rest)
                return [0xC6, v & 0xFF]
        
        # ---- ADC A,r / ADC A,n
        if op == 'ADC':
            if args.upper().startswith('A'):
                rest = args[1:].strip().lstrip(',').strip()
                r = self._reg8(rest)
                if r is not None:
                    return [0x88 | r]
                v = self._eval(rest)
                return [0xCE, v & 0xFF]
        
        # ---- SBC A,r / SBC A,n
        if op == 'SBC':
            if args.upper().startswith('A'):
                rest = args[1:].strip().lstrip(',').strip()
                r = self._reg8(rest)
                if r is not None:
                    return [0x98 | r]
                v = self._eval(rest)
                return [0xDE, v & 0xFF]
        
        # ---- SUB r / SUB n / AND / XOR / OR / CP
        alu = {'SUB': 0x90, 'AND': 0xA0, 'XOR': 0xA8, 'OR': 0xB0, 'CP': 0xB8}
        if op in alu:
            r = self._reg8(args)
            if r is not None:
                return [alu[op] | r]
            v = self._eval(args)
            return [alu[op] | 0x46, v & 0xFF]
        
        # ---- SBC HL,rr / ADC HL,rr  (ED 42+r<<4 / ED 4A+r<<4)
        # Faltavam: sem elas o montador so avisava e seguia, gravando uma ROM
        # com um buraco no lugar da instrucao.
        if op in ('SBC', 'ADC') and args.upper().replace(' ', '').startswith('HL,'):
            r = self._reg16(args.split(',')[1].strip())
            if r is not None:
                return [0xED, (0x42 if op == 'SBC' else 0x4A) | (r << 4)]

        # ---- ADD HL,BC/DE/HL/SP
        if op == 'ADD' and args.upper().startswith('HL,'):
            r = self._reg16(args.split(',')[1].strip())
            if r is not None:
                return [0x09 | (r << 4)]
        
        # ---- ADD IX,BC/DE/IX/SP / ADD IY,BC/DE/IY/SP
        m = re.match(r'ADD\s+(IX|IY)\s*,\s*(BC|DE|SP)', u, re.IGNORECASE)
        if m:
            p = 0xDD if m.group(1).upper() == 'IX' else 0xFD
            r = self._reg16(m.group(2).upper())
            if r is not None:
                return [p, 0x09 | (r << 4)]
        if re.match(r'ADD\s+IX\s*,\s*IX', u, re.IGNORECASE):
            return [0xDD, 0x09 | (2 << 4)]  # IX+IX same encoding as HL+HL within IX prefix

        # ---- BIT/SET/RES n,(HL)
        m = re.match(r'(BIT|SET|RES)\s+(\d+)\s*,\s*\(\s*HL\s*\)', u, re.IGNORECASE)
        if m:
            op2 = m.group(1).upper()
            bit = int(m.group(2))
            base = {'BIT': 0x46, 'SET': 0xC6, 'RES': 0x86}
            return [0xCB, base[op2] | (bit << 3)]
        
        # ---- BIT/SET/RES n,r
        m = re.match(r'(BIT|SET|RES)\s+(\d+)\s*,\s*([A-Z])', u, re.IGNORECASE)
        if m:
            op2 = m.group(1).upper()
            bit = int(m.group(2))
            r = self._reg8(m.group(3))
            if r is not None:
                base = {'BIT': 0x40, 'SET': 0xC0, 'RES': 0x80}
                return [0xCB, base[op2] | (bit << 3) | r]
        
        # ---- RLC/RRC/RL/RR/SLA/SRA/SRL r
        m = re.search(r'(RLC|RRC|RL|RR|SLA|SRA|SRL)\s+([A-Z])', u, re.IGNORECASE)
        if m:
            op2 = m.group(1).upper()
            r = self._reg8(m.group(2))
            if r is not None:
                base = {'RLC': 0x00, 'RRC': 0x08, 'RL': 0x10, 'RR': 0x18,
                        'SLA': 0x20, 'SRA': 0x28, 'SRL': 0x38}
                return [0xCB, base[op2] | r]
        
        # ---- NEG
        if op == 'NEG':
            return [0xED, 0x44]
        
        # ---- LDI / LDIR / LDD / LDDR / CPI / CPIR / CPD / CPDR
        block = {'LDI': 0xA0, 'LDIR': 0xB0, 'LDD': 0xA8, 'LDDR': 0xB8,
                 'CPI': 0xA1, 'CPIR': 0xB1, 'CPD': 0xA9, 'CPDR': 0xB9}
        if op in block:
            return [0xED, block[op]]
        
        # ---- INI / INIR / IND / INDR / OUTI / OTIR / OUTD / OTDR
        io_block = {'INI': 0xA2, 'INIR': 0xB2, 'IND': 0xAA, 'INDR': 0xBA,
                    'OUTI': 0xA3, 'OTIR': 0xB3, 'OUTD': 0xAB, 'OTDR': 0xBB}
        if op in io_block:
            return [0xED, io_block[op]]
        
        # ---- IN A,(n)
        if op == 'IN' and args.upper().startswith('A,'):
            port = self._eval(args.split(',')[1].strip())
            return [0xDB, port & 0xFF]
        
        # ---- OUT (n),A
        if op == 'OUT':
            m = re.match(r'\((.+)\)\s*,\s*A', args, re.IGNORECASE)
            if m:
                port = self._eval(m.group(1))
                return [0xD3, port & 0xFF]
        
        # ---- IN r,(C)
        if op == 'IN':
            m = re.match(r'([A-Z])\s*,\s*\(\s*C\s*\)', args, re.IGNORECASE)
            if m:
                r = self._reg8(m.group(1))
                if r is not None:
                    return [0xED, 0x40 | (r << 3)]
        
        # ---- OUT (C),r
        if op == 'OUT':
            m = re.match(r'\(\s*C\s*\)\s*,\s*([A-Z])', args, re.IGNORECASE)
            if m:
                r = self._reg8(m.group(1))
                if r is not None:
                    return [0xED, 0x41 | (r << 3)]
        
        raise ValueError(f"Unknown instruction: {u}")

    def _guess_size(self, line: str) -> int:
        u = line.strip().upper()
        if u.startswith('JR') or u.startswith('DJNZ'):
            return 2
        if u.startswith('JP') or u.startswith('CALL'):
            return 3
        if u.startswith('LD '):
            if ',' in u:
                dst = u.split(',')[0].strip()
                src = u.split(',')[1].strip()
                if src.startswith('(') or dst.startswith('('):
                    if '(HL)' in src or '(HL)' in dst:
                        return 1
                    if '(BC)' in src or '(DE)' in src or '(BC)' in dst or '(DE)' in dst:
                        return 1
                    return 3
                if dst in ('IX', 'IY') or src in ('IX', 'IY'):
                    return 4
                if dst in ('BC','DE','HL','SP') or src in ('BC','DE','HL','SP'):
                    if dst == 'SP' and src == 'HL':
                        return 1
                    r16 = self._reg16(dst) if self._reg16(dst) is not None else self._reg16(src)
                    if r16 is not None:
                        return 3
                r8 = self._reg8(dst)
                if r8 is not None:
                    if self._reg8(src) is not None:
                        return 1
                    return 2
            return 2
        if u.startswith('PUSH') or u.startswith('POP'):
            return 2 if 'IX' in u or 'IY' in u else 1
        if u.startswith('INC') or u.startswith('DEC'):
            a = u.split()[1] if len(u.split()) > 1 else ''
            if a in ('IX', 'IY'):
                return 2
            if self._reg16(a) is not None:
                return 1
            return 1
        if u.startswith('ADD') or u.startswith('ADC') or u.startswith('SBC'):
            if 'HL,' in u or 'IX,' in u or 'IY,' in u:
                return 2 if ('IX' in u or 'IY' in u) else 1
            if ',' in u:
                return 2
            return 1
        if u.startswith('SUB') or u.startswith('AND') or u.startswith('XOR') or u.startswith('OR') or u.startswith('CP'):
            return 2 if len(u.split()) > 1 and not self._reg8(u.split()[1]) else 1
        if u.startswith('BIT') or u.startswith('SET') or u.startswith('RES'):
            return 2
        if u.startswith('RLC') or u.startswith('RRC') or u.startswith('SLA') or u.startswith('SRA') or u.startswith('SRL'):
            return 2
        if u.startswith('RET') or u.startswith('RST'):
            return 1
        if u.startswith('NEG') or u.startswith('LDI') or u.startswith('LDD') or u.startswith('LDIR') or u.startswith('LDDR'):
            return 2
        if u.startswith('EX'):
            return 1
        if u.startswith('NEG') or u.startswith('IN') or u.startswith('OUT'):
            return 2
        return 1


def assemble_file(source_path: str = None, output_path: str = None, org: int = 0x4000, source_text: str = None, tamanho: int = 32 * 1024):
    """Assemble a .asm file to .rom binary."""
    if source_text is not None:
        source = source_text
    elif source_path is not None:
        with open(source_path) as f:
            source = f.read()
    else:
        raise ValueError("Either source_path or source_text required")
    
    asm = Z80Assembler()
    asm.org = org
    binary = asm.assemble(source)
    
    if output_path:
        # Completa ate o tamanho do cartucho. Passar disso nao e "ficar maior":
        # muda o formato que o WebMSX detecta e o mapeamento vira outro.
        if len(binary) > tamanho:
            raise SystemExit(f'binario com {len(binary)} bytes nao cabe no '
                             f'cartucho de {tamanho} bytes')
        if len(binary) < tamanho:
            binary.extend([0xFF] * (tamanho - len(binary)))
        
        with open(output_path, 'wb') as f:
            f.write(binary)
        
        print(f"Assembled: {len(binary)} bytes -> {output_path}")
        print(f"Equates ({len(asm.equates)}):")
        for name, val in sorted(asm.equates.items(), key=lambda x: x[1]):
            print(f"  {name} = 0x{val:04X}")
        print(f"Labels ({len(asm.labels)}):")
        for name, addr in sorted(asm.labels.items(), key=lambda x: x[1]):
            print(f"  {name}: 0x{addr:04X}")
    else:
        print(f"Assembled: {len(binary)} bytes (no output written)")
        print(f"Labels: {len(asm.labels)}")
    
    return asm.labels, binary


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: minz80asm.py input.asm output.rom [org_hex]")
        sys.exit(1)
    org = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x4000
    assemble_file(sys.argv[1], sys.argv[2], org)
