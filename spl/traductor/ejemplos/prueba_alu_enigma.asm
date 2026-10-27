; Traduccion automatica CacaoCore-64 -> Enigma-64
; Temporales: TMP1=R4  TMP2=R5   Pila: R6   Datos: 0x00201000
; ACC sincronizado: si
; Asignacion de registros:
;   R0         -> derrame [R7 + 24]
;   R1         -> derrame [R7 + 32]
;   R2         -> R3
;   R3         -> derrame [R7 + 48]
;   R4         -> derrame [R7 + 16]
;   R5         -> derrame [R7 + 8]
;   R6         -> derrame [R7 + 64]
;   R7         -> derrame [R7 + 40]
;   R8         -> derrame [R7 + 56]
;   R9         -> derrame [R7 + 72]
;   R10        -> derrame [R7 + 80]
;   R11        -> derrame [R7 + 88]
;   R12        -> R2
;   R13 (SP)   -> R6
;   R14 (LR)   -> derrame [R7]
;   R15 (ACC)  -> R1
    ADDI R7, R0, 0x0030       ; [prologo] BP = area de derrame 0x00300000
    SHL R7, R7, 16            ; [prologo] BP = area de derrame 0x00300000
    ADDI R7, R7, 0x0000       ; [prologo] BP = area de derrame 0x00300000
    ADDI R4, R0, 40           ; [datos] x: 40 -> 0x00201000
    ADDI R5, R0, 0x0020       ; [datos] x: 40 -> 0x00201000
    SHL R5, R5, 16            ; [datos] x: 40 -> 0x00201000
    ADDI R5, R5, 0x1000       ; [datos] x: 40 -> 0x00201000
    STORE R4, [R5]            ; [datos] x: 40 -> 0x00201000
    ADDI R4, R0, 6            ; [datos] y: 6 -> 0x00201008
    ADDI R5, R0, 0x0020       ; [datos] y: 6 -> 0x00201008
    SHL R5, R5, 16            ; [datos] y: 6 -> 0x00201008
    ADDI R5, R5, 0x1008       ; [datos] y: 6 -> 0x00201008
    STORE R4, [R5]            ; [datos] y: 6 -> 0x00201008
    ADDI R5, R0, 0x0020       ; [datos] res: 0 -> 0x00201010
    SHL R5, R5, 16            ; [datos] res: 0 -> 0x00201010
    ADDI R5, R5, 0x1010       ; [datos] res: 0 -> 0x00201010
    STORE R0, [R5]            ; [datos] res: 0 -> 0x00201010
    ADDI R5, R0, 0x0020       ; [datos] fallos: 0 -> 0x00201018
    SHL R5, R5, 16            ; [datos] fallos: 0 -> 0x00201018
    ADDI R5, R5, 0x1018       ; [datos] fallos: 0 -> 0x00201018
    STORE R0, [R5]            ; [datos] fallos: 0 -> 0x00201018
; .data
; .text
    ADD R2, R0, R0            ; L12: MOVD R12, 0
    ADDI R5, R0, 0x0020       ; L13: MOVD R0, [x]
    SHL R5, R5, 16            ; L13: MOVD R0, [x]
    ADDI R5, R5, 0x1000       ; L13: MOVD R0, [x]
    LOAD R4, [R5]             ; L13: MOVD R0, [x]
    STORE R4, [R7 + 24]       ; L13: MOVD R0, [x]
    ADDI R5, R0, 0x0020       ; L14: MOVD R1, [y]
    SHL R5, R5, 16            ; L14: MOVD R1, [y]
    ADDI R5, R5, 0x1008       ; L14: MOVD R1, [y]
    LOAD R4, [R5]             ; L14: MOVD R1, [y]
    STORE R4, [R7 + 32]       ; L14: MOVD R1, [y]
    LOAD R3, [R7 + 24]        ; L17: MOVD R2, R0
    LOAD R5, [R7 + 32]        ; L18: ADD R2, R1
    ADD R1, R3, R5            ; L18: ADD R2, R1
    ADD R3, R3, R5            ; L18: ADD R2, R1
    ADDI R5, R0, 46           ; L19: XOR R2, 46
    XOR R1, R3, R5            ; L19: XOR R2, 46
    XOR R3, R3, R5            ; L19: XOR R2, 46
    OR R1, R2, R3             ; L20: OR R12, R2
    OR R2, R2, R3             ; L20: OR R12, R2
    LOAD R4, [R7 + 24]        ; L21: MOVD R3, R0
    STORE R4, [R7 + 48]       ; L21: MOVD R3, R0
    LOAD R4, [R7 + 48]        ; L22: SUB R3, R1
    LOAD R5, [R7 + 32]        ; L22: SUB R3, R1
    SUB R1, R4, R5            ; L22: SUB R3, R1
    SUB R4, R4, R5            ; L22: SUB R3, R1
    STORE R4, [R7 + 48]       ; L22: SUB R3, R1
    LOAD R4, [R7 + 48]        ; L23: XOR R3, 34
    ADDI R5, R0, 34           ; L23: XOR R3, 34
    XOR R1, R4, R5            ; L23: XOR R3, 34
    XOR R4, R4, R5            ; L23: XOR R3, 34
    STORE R4, [R7 + 48]       ; L23: XOR R3, 34
    LOAD R5, [R7 + 48]        ; L24: OR R12, R3
    OR R1, R2, R5             ; L24: OR R12, R3
    OR R2, R2, R5             ; L24: OR R12, R3
    LOAD R4, [R7 + 24]        ; L25: MOVD R4, R0
    STORE R4, [R7 + 16]       ; L25: MOVD R4, R0
    LOAD R4, [R7 + 16]        ; L26: MUL R4, R1
    LOAD R5, [R7 + 32]        ; L26: MUL R4, R1
    MUL R1, R4, R5            ; L26: MUL R4, R1
    MUL R4, R4, R5            ; L26: MUL R4, R1
    STORE R4, [R7 + 16]       ; L26: MUL R4, R1
    LOAD R4, [R7 + 16]        ; L27: XOR R4, 240
    ADDI R5, R0, 240          ; L27: XOR R4, 240
    XOR R1, R4, R5            ; L27: XOR R4, 240
    XOR R4, R4, R5            ; L27: XOR R4, 240
    STORE R4, [R7 + 16]       ; L27: XOR R4, 240
    LOAD R5, [R7 + 16]        ; L28: OR R12, R4
    OR R1, R2, R5             ; L28: OR R12, R4
    OR R2, R2, R5             ; L28: OR R12, R4
    LOAD R4, [R7 + 24]        ; L29: MOVD R5, R0
    STORE R4, [R7 + 8]        ; L29: MOVD R5, R0
    LOAD R4, [R7 + 32]        ; L30: MOVD R6, R1
    STORE R4, [R7 + 64]       ; L30: MOVD R6, R1
    LOAD R4, [R7 + 8]         ; L31: DIV R5, R6
    LOAD R5, [R7 + 64]        ; L31: DIV R5, R6
    DIV R4, R4, R5            ; L31: DIV R5, R6
    MUL R5, R4, R5            ; L31: DIV R5, R6
    PUSH R4                   ; L31: DIV R5, R6
    LOAD R4, [R7 + 8]         ; L31: DIV R5, R6
    SUB R5, R4, R5            ; L31: DIV R5, R6
    POP R4                    ; L31: DIV R5, R6
    STORE R5, [R7 + 64]       ; L31: DIV R5, R6
    STORE R4, [R7 + 8]        ; L31: DIV R5, R6
    ADD R1, R4, R0            ; L31: DIV R5, R6
    LOAD R4, [R7 + 8]         ; L32: XOR R5, 6
    ADDI R5, R0, 6            ; L32: XOR R5, 6
    XOR R1, R4, R5            ; L32: XOR R5, 6
    XOR R4, R4, R5            ; L32: XOR R5, 6
    STORE R4, [R7 + 8]        ; L32: XOR R5, 6
    LOAD R5, [R7 + 8]         ; L33: OR R12, R5
    OR R1, R2, R5             ; L33: OR R12, R5
    OR R2, R2, R5             ; L33: OR R12, R5
    LOAD R4, [R7 + 64]        ; L34: XOR R6, 4
    ADDI R5, R0, 4            ; L34: XOR R6, 4
    XOR R1, R4, R5            ; L34: XOR R6, 4
    XOR R4, R4, R5            ; L34: XOR R6, 4
    STORE R4, [R7 + 64]       ; L34: XOR R6, 4
    LOAD R5, [R7 + 64]        ; L35: OR R12, R6
    OR R1, R2, R5             ; L35: OR R12, R6
    OR R2, R2, R5             ; L35: OR R12, R6
    ADDI R4, R0, 12           ; L36: MOVD R7, 12
    STORE R4, [R7 + 40]       ; L36: MOVD R7, 12
    ADDI R4, R0, 10           ; L37: MOVD R8, 10
    STORE R4, [R7 + 56]       ; L37: MOVD R8, 10
    LOAD R4, [R7 + 40]        ; L38: AND R7, R8
    LOAD R5, [R7 + 56]        ; L38: AND R7, R8
    AND R1, R4, R5            ; L38: AND R7, R8
    AND R4, R4, R5            ; L38: AND R7, R8
    STORE R4, [R7 + 40]       ; L38: AND R7, R8
    LOAD R4, [R7 + 40]        ; L39: XOR R7, 8
    ADDI R5, R0, 8            ; L39: XOR R7, 8
    XOR R1, R4, R5            ; L39: XOR R7, 8
    XOR R4, R4, R5            ; L39: XOR R7, 8
    STORE R4, [R7 + 40]       ; L39: XOR R7, 8
    LOAD R5, [R7 + 40]        ; L40: OR R12, R7
    OR R1, R2, R5             ; L40: OR R12, R7
    OR R2, R2, R5             ; L40: OR R12, R7
    ADDI R4, R0, 12           ; L41: MOVD R8, 12
    STORE R4, [R7 + 56]       ; L41: MOVD R8, 12
    ADDI R4, R0, 3            ; L42: MOVD R9, 3
    STORE R4, [R7 + 72]       ; L42: MOVD R9, 3
    LOAD R4, [R7 + 56]        ; L43: OR R8, R9
    LOAD R5, [R7 + 72]        ; L43: OR R8, R9
    OR R1, R4, R5             ; L43: OR R8, R9
    OR R4, R4, R5             ; L43: OR R8, R9
    STORE R4, [R7 + 56]       ; L43: OR R8, R9
    LOAD R4, [R7 + 56]        ; L44: XOR R8, 15
    ADDI R5, R0, 15           ; L44: XOR R8, 15
    XOR R1, R4, R5            ; L44: XOR R8, 15
    XOR R4, R4, R5            ; L44: XOR R8, 15
    STORE R4, [R7 + 56]       ; L44: XOR R8, 15
    LOAD R5, [R7 + 56]        ; L45: OR R12, R8
    OR R1, R2, R5             ; L45: OR R12, R8
    OR R2, R2, R5             ; L45: OR R12, R8
    ADDI R4, R0, 12           ; L46: MOVD R9, 12
    STORE R4, [R7 + 72]       ; L46: MOVD R9, 12
    LOAD R4, [R7 + 72]        ; L47: XOR R9, R1
    LOAD R5, [R7 + 32]        ; L47: XOR R9, R1
    XOR R1, R4, R5            ; L47: XOR R9, R1
    XOR R4, R4, R5            ; L47: XOR R9, R1
    STORE R4, [R7 + 72]       ; L47: XOR R9, R1
    LOAD R4, [R7 + 72]        ; L48: XOR R9, 10
    ADDI R5, R0, 10           ; L48: XOR R9, 10
    XOR R1, R4, R5            ; L48: XOR R9, 10
    XOR R4, R4, R5            ; L48: XOR R9, 10
    STORE R4, [R7 + 72]       ; L48: XOR R9, 10
    LOAD R5, [R7 + 72]        ; L49: OR R12, R9
    OR R1, R2, R5             ; L49: OR R12, R9
    OR R2, R2, R5             ; L49: OR R12, R9
    ADDI R3, R0, 46           ; L52: MOVD R2, 46
    ADDI R1, R3, 4            ; L53: ADD R2, 4
    ADDI R3, R3, 4            ; L53: ADD R2, 4
    ADDI R5, R0, 50           ; L54: XOR R2, 50
    XOR R1, R3, R5            ; L54: XOR R2, 50
    XOR R3, R3, R5            ; L54: XOR R2, 50
    OR R1, R2, R3             ; L55: OR R12, R2
    OR R2, R2, R3             ; L55: OR R12, R2
    ADDI R4, R0, 34           ; L56: MOVD R3, 34
    STORE R4, [R7 + 48]       ; L56: MOVD R3, 34
    LOAD R4, [R7 + 48]        ; L57: SUB R3, 40000
    ADDI R5, R0, 1            ; L57: SUB R3, 40000
    SHL R5, R5, 16            ; L57: SUB R3, 40000
    ADDI R5, R5, -25536       ; L57: SUB R3, 40000
    SUB R1, R4, R5            ; L57: SUB R3, 40000
    SUB R4, R4, R5            ; L57: SUB R3, 40000
    STORE R4, [R7 + 48]       ; L57: SUB R3, 40000
    LOAD R4, [R7 + 48]        ; L58: XOR R3, -39966
    ADDI R5, R0, -1           ; L58: XOR R3, -39966
    SHL R5, R5, 16            ; L58: XOR R3, -39966
    ADDI R5, R5, 25570        ; L58: XOR R3, -39966
    XOR R1, R4, R5            ; L58: XOR R3, -39966
    XOR R4, R4, R5            ; L58: XOR R3, -39966
    STORE R4, [R7 + 48]       ; L58: XOR R3, -39966
    LOAD R5, [R7 + 48]        ; L59: OR R12, R3
    OR R1, R2, R5             ; L59: OR R12, R3
    OR R2, R2, R5             ; L59: OR R12, R3
    ADDI R4, R0, 240          ; L60: MOVD R4, 240
    STORE R4, [R7 + 16]       ; L60: MOVD R4, 240
    LOAD R4, [R7 + 16]        ; L61: MUL R4, -2
    ADDI R5, R0, -2           ; L61: MUL R4, -2
    MUL R1, R4, R5            ; L61: MUL R4, -2
    MUL R4, R4, R5            ; L61: MUL R4, -2
    STORE R4, [R7 + 16]       ; L61: MUL R4, -2
    LOAD R4, [R7 + 16]        ; L62: XOR R4, -480
    ADDI R5, R0, -480         ; L62: XOR R4, -480
    XOR R1, R4, R5            ; L62: XOR R4, -480
    XOR R4, R4, R5            ; L62: XOR R4, -480
    STORE R4, [R7 + 16]       ; L62: XOR R4, -480
    LOAD R5, [R7 + 16]        ; L63: OR R12, R4
    OR R1, R2, R5             ; L63: OR R12, R4
    OR R2, R2, R5             ; L63: OR R12, R4
    ADDI R4, R0, 6            ; L64: MOVD R5, 6
    STORE R4, [R7 + 8]        ; L64: MOVD R5, 6
    LOAD R4, [R7 + 8]         ; L65: DIV R5, 4
    ADDI R5, R0, 4            ; L65: DIV R5, 4
    DIV R1, R4, R5            ; L65: DIV R5, 4
    DIV R4, R4, R5            ; L65: DIV R5, 4
    STORE R4, [R7 + 8]        ; L65: DIV R5, 4
    LOAD R4, [R7 + 8]         ; L66: XOR R5, 1
    ADDI R5, R0, 1            ; L66: XOR R5, 1
    XOR R1, R4, R5            ; L66: XOR R5, 1
    XOR R4, R4, R5            ; L66: XOR R5, 1
    STORE R4, [R7 + 8]        ; L66: XOR R5, 1
    LOAD R5, [R7 + 8]         ; L67: OR R12, R5
    OR R1, R2, R5             ; L67: OR R12, R5
    OR R2, R2, R5             ; L67: OR R12, R5
    ADDI R3, R0, 50           ; L70: MOVD R2, 50
    ADDI R5, R0, 0x0020       ; L71: ADD R2, [y]
    SHL R5, R5, 16            ; L71: ADD R2, [y]
    ADDI R5, R5, 0x1008       ; L71: ADD R2, [y]
    LOAD R5, [R5]             ; L71: ADD R2, [y]
    ADD R1, R3, R5            ; L71: ADD R2, [y]
    ADD R3, R3, R5            ; L71: ADD R2, [y]
    ADDI R5, R0, 56           ; L72: XOR R2, 56
    XOR R1, R3, R5            ; L72: XOR R2, 56
    XOR R3, R3, R5            ; L72: XOR R2, 56
    OR R1, R2, R3             ; L73: OR R12, R2
    OR R2, R2, R3             ; L73: OR R12, R2
    ADDI R4, R0, 8            ; L74: MOVD R7, 8
    STORE R4, [R7 + 40]       ; L74: MOVD R7, 8
    LOAD R4, [R7 + 40]        ; L75: MUL R7, [y]
    ADDI R5, R0, 0x0020       ; L75: MUL R7, [y]
    SHL R5, R5, 16            ; L75: MUL R7, [y]
    ADDI R5, R5, 0x1008       ; L75: MUL R7, [y]
    LOAD R5, [R5]             ; L75: MUL R7, [y]
    MUL R1, R4, R5            ; L75: MUL R7, [y]
    MUL R4, R4, R5            ; L75: MUL R7, [y]
    STORE R4, [R7 + 40]       ; L75: MUL R7, [y]
    LOAD R4, [R7 + 40]        ; L76: XOR R7, 48
    ADDI R5, R0, 48           ; L76: XOR R7, 48
    XOR R1, R4, R5            ; L76: XOR R7, 48
    XOR R4, R4, R5            ; L76: XOR R7, 48
    STORE R4, [R7 + 40]       ; L76: XOR R7, 48
    LOAD R5, [R7 + 40]        ; L77: OR R12, R7
    OR R1, R2, R5             ; L77: OR R12, R7
    OR R2, R2, R5             ; L77: OR R12, R7
    ADDI R4, R0, 15           ; L78: MOVD R8, 15
    STORE R4, [R7 + 56]       ; L78: MOVD R8, 15
    LOAD R4, [R7 + 56]        ; L79: AND R8, [x]
    ADDI R5, R0, 0x0020       ; L79: AND R8, [x]
    SHL R5, R5, 16            ; L79: AND R8, [x]
    ADDI R5, R5, 0x1000       ; L79: AND R8, [x]
    LOAD R5, [R5]             ; L79: AND R8, [x]
    AND R1, R4, R5            ; L79: AND R8, [x]
    AND R4, R4, R5            ; L79: AND R8, [x]
    STORE R4, [R7 + 56]       ; L79: AND R8, [x]
    LOAD R4, [R7 + 56]        ; L80: XOR R8, 8
    ADDI R5, R0, 8            ; L80: XOR R8, 8
    XOR R1, R4, R5            ; L80: XOR R8, 8
    XOR R4, R4, R5            ; L80: XOR R8, 8
    STORE R4, [R7 + 56]       ; L80: XOR R8, 8
    LOAD R5, [R7 + 56]        ; L81: OR R12, R8
    OR R1, R2, R5             ; L81: OR R12, R8
    OR R2, R2, R5             ; L81: OR R12, R8
    ADDI R4, R0, 0x0020       ; L82: LEA R10, [x]
    SHL R4, R4, 16            ; L82: LEA R10, [x]
    ADDI R4, R4, 0x1000       ; L82: LEA R10, [x]
    STORE R4, [R7 + 80]       ; L82: LEA R10, [x]
    ADD R1, R4, R0            ; L82: LEA R10, [x]
    ADDI R3, R0, 56           ; L83: MOVD R2, 56
    LOAD R5, [R7 + 80]        ; L84: ADD R2, [R10]
    LOAD R5, [R5]             ; L84: ADD R2, [R10]
    ADD R1, R3, R5            ; L84: ADD R2, [R10]
    ADD R3, R3, R5            ; L84: ADD R2, [R10]
    ADDI R5, R0, 96           ; L85: XOR R2, 96
    XOR R1, R3, R5            ; L85: XOR R2, 96
    XOR R3, R3, R5            ; L85: XOR R2, 96
    OR R1, R2, R3             ; L86: OR R12, R2
    OR R2, R2, R3             ; L86: OR R12, R2
    ADDI R1, R0, 100          ; L89: LOADD 100
    LOAD R5, [R7 + 32]        ; L90: ADD R1
    ADD R1, R1, R5            ; L90: ADD R1
    SUBI R1, R1, 6            ; L91: SUB 6
    ADDI R5, R0, 0x0020       ; L92: MUL [y]
    SHL R5, R5, 16            ; L92: MUL [y]
    ADDI R5, R5, 0x1008       ; L92: MUL [y]
    LOAD R5, [R5]             ; L92: MUL [y]
    MUL R1, R1, R5            ; L92: MUL [y]
    ADDI R5, R0, 7            ; L93: DIV 7
    DIV R1, R1, R5            ; L93: DIV 7
    ADDI R5, R0, 255          ; L94: AND 255
    AND R1, R1, R5            ; L94: AND 255
    ADDI R5, R0, 2            ; L95: OR 2
    OR R1, R1, R5             ; L95: OR 2
    LOAD R5, [R7 + 32]        ; L96: XOR R1
    XOR R1, R1, R5            ; L96: XOR R1
    STORE R1, [R7]            ; L97: STORED R14
    LOAD R4, [R7]             ; L98: XOR R14, 81
    ADDI R5, R0, 81           ; L98: XOR R14, 81
    XOR R1, R4, R5            ; L98: XOR R14, 81
    XOR R4, R4, R5            ; L98: XOR R14, 81
    STORE R4, [R7]            ; L98: XOR R14, 81
    LOAD R5, [R7]             ; L99: OR R12, R14
    OR R1, R2, R5             ; L99: OR R12, R14
    OR R2, R2, R5             ; L99: OR R12, R14
    ADDI R3, R0, 10           ; L102: MOVD R2, 10
    ADDI R1, R3, 1            ; L103: INC R2
    INC R3                    ; L103: INC R2
    SUB R1, R0, R3            ; L104: NEG R2
    SUB R3, R0, R3            ; L104: NEG R2
    ADD R1, R3, R0            ; L105: NOT R2
    NOT R1                    ; L105: NOT R2
    NOT R3                    ; L105: NOT R2
    SUBI R1, R3, 1            ; L106: DEC R2
    DEC R3                    ; L106: DEC R2
    STORE R1, [R7]            ; L107: STORED R14
    ADDI R5, R0, 9            ; L108: XOR R2, 9
    XOR R1, R3, R5            ; L108: XOR R2, 9
    XOR R3, R3, R5            ; L108: XOR R2, 9
    OR R1, R2, R3             ; L109: OR R12, R2
    OR R2, R2, R3             ; L109: OR R12, R2
    LOAD R4, [R7]             ; L110: XOR R14, 9
    ADDI R5, R0, 9            ; L110: XOR R14, 9
    XOR R1, R4, R5            ; L110: XOR R14, 9
    XOR R4, R4, R5            ; L110: XOR R14, 9
    STORE R4, [R7]            ; L110: XOR R14, 9
    LOAD R5, [R7]             ; L111: OR R12, R14
    OR R1, R2, R5             ; L111: OR R12, R14
    OR R2, R2, R5             ; L111: OR R12, R14
    ADDI R5, R0, 0x0020       ; L114: INC [res]
    SHL R5, R5, 16            ; L114: INC [res]
    ADDI R5, R5, 0x1010       ; L114: INC [res]
    LOAD R4, [R5]             ; L114: INC [res]
    ADDI R1, R4, 1            ; L114: INC [res]
    INC R4                    ; L114: INC [res]
    STORE R4, [R5]            ; L114: INC [res]
    ADDI R5, R0, 0x0020       ; L115: NEG [res]
    SHL R5, R5, 16            ; L115: NEG [res]
    ADDI R5, R5, 0x1010       ; L115: NEG [res]
    LOAD R4, [R5]             ; L115: NEG [res]
    SUB R1, R0, R4            ; L115: NEG [res]
    SUB R4, R0, R4            ; L115: NEG [res]
    STORE R4, [R5]            ; L115: NEG [res]
    ADDI R5, R0, 0x0020       ; L116: NOT [res]
    SHL R5, R5, 16            ; L116: NOT [res]
    ADDI R5, R5, 0x1010       ; L116: NOT [res]
    LOAD R4, [R5]             ; L116: NOT [res]
    ADD R1, R4, R0            ; L116: NOT [res]
    NOT R1                    ; L116: NOT [res]
    NOT R4                    ; L116: NOT [res]
    STORE R4, [R5]            ; L116: NOT [res]
    ADDI R5, R0, 0x0020       ; L117: DEC [res]
    SHL R5, R5, 16            ; L117: DEC [res]
    ADDI R5, R5, 0x1010       ; L117: DEC [res]
    LOAD R4, [R5]             ; L117: DEC [res]
    SUBI R1, R4, 1            ; L117: DEC [res]
    DEC R4                    ; L117: DEC [res]
    STORE R4, [R5]            ; L117: DEC [res]
    ADDI R5, R0, 0x0020       ; L118: MOVD R3, [res]
    SHL R5, R5, 16            ; L118: MOVD R3, [res]
    ADDI R5, R5, 0x1010       ; L118: MOVD R3, [res]
    LOAD R4, [R5]             ; L118: MOVD R3, [res]
    STORE R4, [R7 + 48]       ; L118: MOVD R3, [res]
    LOAD R4, [R7 + 48]        ; L119: XOR R3, -1
    ADDI R5, R0, -1           ; L119: XOR R3, -1
    XOR R1, R4, R5            ; L119: XOR R3, -1
    XOR R4, R4, R5            ; L119: XOR R3, -1
    STORE R4, [R7 + 48]       ; L119: XOR R3, -1
    LOAD R5, [R7 + 48]        ; L120: OR R12, R3
    OR R1, R2, R5             ; L120: OR R12, R3
    OR R2, R2, R5             ; L120: OR R12, R3
    ADDI R4, R0, -64          ; L123: MOVD R4, -64
    STORE R4, [R7 + 16]       ; L123: MOVD R4, -64
    LOAD R4, [R7 + 16]        ; L124: SHR R4, 3
    ASR R1, R4, 3             ; L124: SHR R4, 3
    ASR R4, R4, 3             ; L124: SHR R4, 3
    STORE R4, [R7 + 16]       ; L124: SHR R4, 3
    LOAD R4, [R7 + 16]        ; L125: SHL R4, 4
    SHL R1, R4, 4             ; L125: SHL R4, 4
    SHL R4, R4, 4             ; L125: SHL R4, 4
    STORE R4, [R7 + 16]       ; L125: SHL R4, 4
    LOAD R4, [R7 + 16]        ; L126: XOR R4, -128
    ADDI R5, R0, -128         ; L126: XOR R4, -128
    XOR R1, R4, R5            ; L126: XOR R4, -128
    XOR R4, R4, R5            ; L126: XOR R4, -128
    STORE R4, [R7 + 16]       ; L126: XOR R4, -128
    LOAD R5, [R7 + 16]        ; L127: OR R12, R4
    OR R1, R2, R5             ; L127: OR R12, R4
    OR R2, R2, R5             ; L127: OR R12, R4
    ADDI R1, R0, 3            ; L128: LOADD 3
    SHL R1, R1, 5             ; L129: SHL 5
    ASR R1, R1, 2             ; L130: SHR 2
    STORE R1, [R7]            ; L131: STORED R14
    LOAD R4, [R7]             ; L132: XOR R14, 24
    ADDI R5, R0, 24           ; L132: XOR R14, 24
    XOR R1, R4, R5            ; L132: XOR R14, 24
    XOR R4, R4, R5            ; L132: XOR R14, 24
    STORE R4, [R7]            ; L132: XOR R14, 24
    LOAD R5, [R7]             ; L133: OR R12, R14
    OR R1, R2, R5             ; L133: OR R12, R14
    OR R2, R2, R5             ; L133: OR R12, R14
    ADDI R4, R0, 1            ; L134: MOVD R5, 1
    STORE R4, [R7 + 8]        ; L134: MOVD R5, 1
    LOAD R4, [R7 + 8]         ; L135: ROR R5, 1
    SHL R5, R4, 63            ; L135: ROR R5, 1
    SHR R4, R4, 1             ; L135: ROR R5, 1
    OR R4, R4, R5             ; L135: ROR R5, 1
    STORE R4, [R7 + 8]        ; L135: ROR R5, 1
    LOAD R4, [R7 + 8]         ; L136: ROL R5, 2
    SHR R5, R4, 62            ; L136: ROL R5, 2
    SHL R4, R4, 2             ; L136: ROL R5, 2
    OR R4, R4, R5             ; L136: ROL R5, 2
    STORE R4, [R7 + 8]        ; L136: ROL R5, 2
    LOAD R4, [R7 + 8]         ; L137: ROL R5, 64
    STORE R4, [R7 + 8]        ; L137: ROL R5, 64
    LOAD R4, [R7 + 8]         ; L138: XOR R5, 2
    ADDI R5, R0, 2            ; L138: XOR R5, 2
    XOR R1, R4, R5            ; L138: XOR R5, 2
    XOR R4, R4, R5            ; L138: XOR R5, 2
    STORE R4, [R7 + 8]        ; L138: XOR R5, 2
    LOAD R5, [R7 + 8]         ; L139: OR R12, R5
    OR R1, R2, R5             ; L139: OR R12, R5
    OR R2, R2, R5             ; L139: OR R12, R5
    ADDI R1, R0, 1            ; L140: LOADD 1
    SHL R5, R1, 60            ; L141: ROR 4
    SHR R1, R1, 4             ; L141: ROR 4
    OR R1, R1, R5             ; L141: ROR 4
    STORE R1, [R7]            ; L142: STORED R14
    LOAD R4, [R7]             ; L143: SHR R14, 60
    ASR R1, R4, 60            ; L143: SHR R14, 60
    ASR R4, R4, 60            ; L143: SHR R14, 60
    STORE R4, [R7]            ; L143: SHR R14, 60
    LOAD R4, [R7]             ; L144: XOR R14, 1
    ADDI R5, R0, 1            ; L144: XOR R14, 1
    XOR R1, R4, R5            ; L144: XOR R14, 1
    XOR R4, R4, R5            ; L144: XOR R14, 1
    STORE R4, [R7]            ; L144: XOR R14, 1
    LOAD R5, [R7]             ; L145: OR R12, R14
    OR R1, R2, R5             ; L145: OR R12, R14
    OR R2, R2, R5             ; L145: OR R12, R14
    ADDI R4, R0, 111          ; L148: MOVD R6, 111
    STORE R4, [R7 + 64]       ; L148: MOVD R6, 111
    ADDI R4, R0, 222          ; L149: MOVD R7, 222
    STORE R4, [R7 + 40]       ; L149: MOVD R7, 222
    LOAD R4, [R7 + 64]        ; L150: SWAP R6, R7
    LOAD R5, [R7 + 40]        ; L150: SWAP R6, R7
    PUSH R4                   ; L150: SWAP R6, R7
    PUSH R5                   ; L150: SWAP R6, R7
    POP R4                    ; L150: SWAP R6, R7
    POP R5                    ; L150: SWAP R6, R7
    STORE R4, [R7 + 64]       ; L150: SWAP R6, R7
    STORE R5, [R7 + 40]       ; L150: SWAP R6, R7
    LOAD R4, [R7 + 64]        ; L151: XOR R6, 222
    ADDI R5, R0, 222          ; L151: XOR R6, 222
    XOR R1, R4, R5            ; L151: XOR R6, 222
    XOR R4, R4, R5            ; L151: XOR R6, 222
    STORE R4, [R7 + 64]       ; L151: XOR R6, 222
    LOAD R5, [R7 + 64]        ; L152: OR R12, R6
    OR R1, R2, R5             ; L152: OR R12, R6
    OR R2, R2, R5             ; L152: OR R12, R6
    ADDI R1, R0, 333          ; L153: LOADD 333
    LOAD R4, [R7 + 40]        ; L154: SWAP R7
    PUSH R4                   ; L154: SWAP R7
    PUSH R1                   ; L154: SWAP R7
    POP R4                    ; L154: SWAP R7
    POP R1                    ; L154: SWAP R7
    STORE R4, [R7 + 40]       ; L154: SWAP R7
    STORE R1, [R7]            ; L155: STORED R14
    LOAD R4, [R7 + 40]        ; L156: XOR R7, 333
    ADDI R5, R0, 333          ; L156: XOR R7, 333
    XOR R1, R4, R5            ; L156: XOR R7, 333
    XOR R4, R4, R5            ; L156: XOR R7, 333
    STORE R4, [R7 + 40]       ; L156: XOR R7, 333
    LOAD R5, [R7 + 40]        ; L157: OR R12, R7
    OR R1, R2, R5             ; L157: OR R12, R7
    OR R2, R2, R5             ; L157: OR R12, R7
    LOAD R4, [R7]             ; L158: XOR R14, 111
    ADDI R5, R0, 111          ; L158: XOR R14, 111
    XOR R1, R4, R5            ; L158: XOR R14, 111
    XOR R4, R4, R5            ; L158: XOR R14, 111
    STORE R4, [R7]            ; L158: XOR R14, 111
    LOAD R5, [R7]             ; L159: OR R12, R14
    OR R1, R2, R5             ; L159: OR R12, R14
    OR R2, R2, R5             ; L159: OR R12, R14
    ADDI R4, R0, 100          ; L162: MOVD R10, 100
    STORE R4, [R7 + 80]       ; L162: MOVD R10, 100
    ADDI R4, R0, 7            ; L163: MOVD R11, 7
    STORE R4, [R7 + 88]       ; L163: MOVD R11, 7
    LOAD R4, [R7 + 80]        ; L164: DIV R10, R11
    LOAD R5, [R7 + 88]        ; L164: DIV R10, R11
    DIV R4, R4, R5            ; L164: DIV R10, R11
    MUL R5, R4, R5            ; L164: DIV R10, R11
    PUSH R4                   ; L164: DIV R10, R11
    LOAD R4, [R7 + 80]        ; L164: DIV R10, R11
    SUB R5, R4, R5            ; L164: DIV R10, R11
    POP R4                    ; L164: DIV R10, R11
    STORE R5, [R7 + 88]       ; L164: DIV R10, R11
    STORE R4, [R7 + 80]       ; L164: DIV R10, R11
    ADD R1, R4, R0            ; L164: DIV R10, R11
    LOAD R4, [R7 + 80]        ; L165: XOR R10, 14
    ADDI R5, R0, 14           ; L165: XOR R10, 14
    XOR R1, R4, R5            ; L165: XOR R10, 14
    XOR R4, R4, R5            ; L165: XOR R10, 14
    STORE R4, [R7 + 80]       ; L165: XOR R10, 14
    LOAD R5, [R7 + 80]        ; L166: OR R12, R10
    OR R1, R2, R5             ; L166: OR R12, R10
    OR R2, R2, R5             ; L166: OR R12, R10
    LOAD R4, [R7 + 88]        ; L167: XOR R11, 2
    ADDI R5, R0, 2            ; L167: XOR R11, 2
    XOR R1, R4, R5            ; L167: XOR R11, 2
    XOR R4, R4, R5            ; L167: XOR R11, 2
    STORE R4, [R7 + 88]       ; L167: XOR R11, 2
    LOAD R5, [R7 + 88]        ; L168: OR R12, R11
    OR R1, R2, R5             ; L168: OR R12, R11
    OR R2, R2, R5             ; L168: OR R12, R11
    LOAD R4, [R7 + 24]        ; L171: CMP R0, R1
    LOAD R5, [R7 + 32]        ; L171: CMP R0, R1
    CMP R4, R5                ; L171: CMP R0, R1
    JP OK1                    ; L172: JG OK1
    ADDI R1, R2, 1            ; L173: INC R12
    INC R2                    ; L173: INC R12
OK1:
    LOAD R4, [R7 + 32]        ; L175: CMP R1, R0
    LOAD R5, [R7 + 24]        ; L175: CMP R1, R0
    CMP R4, R5                ; L175: CMP R1, R0
    JN OK2                    ; L176: JL OK2
    ADDI R1, R2, 1            ; L177: INC R12
    INC R2                    ; L177: INC R12
OK2:
    LOAD R4, [R7 + 24]        ; L179: CMP R0, 40
    ADDI R5, R0, 40           ; L179: CMP R0, 40
    CMP R4, R5                ; L179: CMP R0, 40
    JZ OK3                    ; L180: JZ OK3
    ADDI R1, R2, 1            ; L181: INC R12
    INC R2                    ; L181: INC R12
OK3:
    LOAD R4, [R7 + 24]        ; L183: TEST R0, 7
    ADDI R5, R0, 7            ; L183: TEST R0, 7
    AND R4, R4, R5            ; L183: TEST R0, 7
    JZ OK4                    ; L184: JZ OK4
    ADDI R1, R2, 1            ; L185: INC R12
    INC R2                    ; L185: INC R12
OK4:
    LOAD R4, [R7 + 24]        ; L187: TEST R0, 8
    ADDI R5, R0, 8            ; L187: TEST R0, 8
    AND R4, R4, R5            ; L187: TEST R0, 8
    JNZ OK5                   ; L188: JNZ OK5
    ADDI R1, R2, 1            ; L189: INC R12
    INC R2                    ; L189: INC R12
OK5:
    LOAD R4, [R7 + 32]        ; L191: CMPZ R1
    CMP R0, R4                ; L191: CMPZ R1
    JN OK6                    ; L192: JS OK6
    ADDI R1, R2, 1            ; L193: INC R12
    INC R2                    ; L193: INC R12
OK6:
    STORE R0, [R7 + 72]       ; L195: MOVD R9, 0
    LOAD R4, [R7 + 72]        ; L196: CMPZ R9
    CMP R0, R4                ; L196: CMPZ R9
    JZ OK7                    ; L197: JZ OK7
    ADDI R1, R2, 1            ; L198: INC R12
    INC R2                    ; L198: INC R12
OK7:
    LOAD R4, [R7 + 32]        ; L200: CMP R1, R0
    LOAD R5, [R7 + 24]        ; L200: CMP R1, R0
    CMP R4, R5                ; L200: CMP R1, R0
    JP MAL8                   ; L201: JGE MAL8
    JZ MAL8                   ; L201: JGE MAL8
    JMP OK8                   ; L202: JMP OK8
MAL8:
    ADDI R1, R2, 1            ; L204: INC R12
    INC R2                    ; L204: INC R12
OK8:
    ADDI R1, R0, 5            ; L206: LOADD 5
    ADDI R5, R0, 5            ; L207: CMP 5
    CMP R1, R5                ; L207: CMP 5
    JZ OK9                    ; L208: JZ OK9
    ADDI R1, R2, 1            ; L209: INC R12
    INC R2                    ; L209: INC R12
OK9:
    ADDI R5, R0, 0x0020       ; L211: TEST [x]
    SHL R5, R5, 16            ; L211: TEST [x]
    ADDI R5, R5, 0x1000       ; L211: TEST [x]
    LOAD R5, [R5]             ; L211: TEST [x]
    AND R4, R1, R5            ; L211: TEST [x]
    JZ OK10                   ; L212: JZ OK10
    ADDI R1, R2, 1            ; L213: INC R12
    INC R2                    ; L213: INC R12
OK10:
    LOAD R4, [R7 + 24]        ; L215: CMP R0, [x]
    ADDI R5, R0, 0x0020       ; L215: CMP R0, [x]
    SHL R5, R5, 16            ; L215: CMP R0, [x]
    ADDI R5, R5, 0x1000       ; L215: CMP R0, [x]
    LOAD R5, [R5]             ; L215: CMP R0, [x]
    CMP R4, R5                ; L215: CMP R0, [x]
    JZ OK11                   ; L216: JZ OK11
    ADDI R1, R2, 1            ; L217: INC R12
    INC R2                    ; L217: INC R12
OK11:
    ADDI R5, R0, 0x0020       ; L219: CMPZ [y]
    SHL R5, R5, 16            ; L219: CMPZ [y]
    ADDI R5, R5, 0x1008       ; L219: CMPZ [y]
    LOAD R4, [R5]             ; L219: CMPZ [y]
    CMP R0, R4                ; L219: CMPZ [y]
    JN OK12                   ; L220: JLE OK12
    JZ OK12                   ; L220: JLE OK12
    ADDI R1, R2, 1            ; L221: INC R12
    INC R2                    ; L221: INC R12
OK12:
    LOAD R4, [R7 + 24]        ; L224: CMP R0, R1
    LOAD R5, [R7 + 32]        ; L224: CMP R0, R1
    CMP R4, R5                ; L224: CMP R0, R1
    PUSH SR                   ; L225: MOVD R2, 12345
    ADDI R3, R0, 12345        ; L225: MOVD R2, 12345
    POP SR                    ; L225: MOVD R2, 12345
    LOAD R4, [R7 + 48]        ; L226: SWAP R3, R4
    LOAD R5, [R7 + 16]        ; L226: SWAP R3, R4
    PUSH R4                   ; L226: SWAP R3, R4
    PUSH R5                   ; L226: SWAP R3, R4
    POP R4                    ; L226: SWAP R3, R4
    POP R5                    ; L226: SWAP R3, R4
    STORE R4, [R7 + 48]       ; L226: SWAP R3, R4
    STORE R5, [R7 + 16]       ; L226: SWAP R3, R4
    PUSH SR                   ; L227: ROL R5, 3
    LOAD R4, [R7 + 8]         ; L227: ROL R5, 3
    SHR R5, R4, 61            ; L227: ROL R5, 3
    SHL R4, R4, 3             ; L227: ROL R5, 3
    OR R4, R4, R5             ; L227: ROL R5, 3
    STORE R4, [R7 + 8]        ; L227: ROL R5, 3
    POP SR                    ; L227: ROL R5, 3
    PUSH SR                   ; L228: LEA R11, [res]
    ADDI R4, R0, 0x0020       ; L228: LEA R11, [res]
    SHL R4, R4, 16            ; L228: LEA R11, [res]
    ADDI R4, R4, 0x1010       ; L228: LEA R11, [res]
    STORE R4, [R7 + 88]       ; L228: LEA R11, [res]
    ADD R1, R4, R0            ; L228: LEA R11, [res]
    POP SR                    ; L228: LEA R11, [res]
    JP OK13                   ; L229: JG OK13
    ADDI R1, R2, 1            ; L230: INC R12
    INC R2                    ; L230: INC R12
OK13:
    ADDI R5, R0, 0x0020       ; L232: MOVD [fallos], R12
    SHL R5, R5, 16            ; L232: MOVD [fallos], R12
    ADDI R5, R5, 0x1018       ; L232: MOVD [fallos], R12
    STORE R2, [R5]            ; L232: MOVD [fallos], R12
    HLT                       ; L233: HLT
