from enigma64 import ALU, BancoRegistros, hex64

# realizar 5!

banco, alu = BancoRegistros(), ALU()
banco.escribir_nombre("R2", 5)   # N = 5
banco.escribir_nombre("R3", 1)   # factorial = 1

paso = 0
while True:
    r = alu.ejecutar("MUL", banco.leer_nombre("R3"), banco.leer_nombre("R2"))
    banco.aplicar_banderas(r.banderas, r.afectadas)
    banco.escribir_nombre("R3", r.valor)

    r = alu.ejecutar("SUBI", banco.leer_nombre("R2"), 1)
    banco.aplicar_banderas(r.banderas, r.afectadas)
    banco.escribir_nombre("R2", r.valor)

    paso += 1
    print(f"Iteracion {paso}: R3={banco.leer_nombre('R3'):>3}  "
          f"R2={banco.leer_nombre('R2')}  Z={banco.leer_bandera('Z')}")

    if banco.leer_bandera("Z"):   # JNZ no bifurca
        break

print(f"\nResultado: {hex64(banco.leer_nombre('R3'))}  (esperado 0x...0078)")
