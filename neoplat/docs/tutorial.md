# Tu primer juego en 10 minutos

## 1. Crea el proyecto

```bash
./ngplat nuevo mijuego --titulo "MI JUEGO" --autor "TU NOMBRE"
cd mijuego
```

Ya tienes un juego completo: dos niveles, un héroe, dos enemigos y monedas.

## 2. Pruébalo

```bash
../ngplat probar
```

Se abre el navegador con el juego. Flechas para moverte, <kbd>Z</kbd> para
saltar, <kbd>Enter</kbd> para empezar. **Esto es exactamente lo que hará la
consola**: la simulación es la misma.

## 3. Cambia el mapa (con el ratón)

En el preview, pulsa <kbd>E</kbd>. Aparece el editor: eliges qué pintar en la
paleta de abajo (suelo, plataformas, pinchos, enemigos, monedas, la salida) y
pintas sobre el nivel. <kbd>Enter</kbd> lo prueba al momento y <kbd>E</kbd> te
devuelve al editor.

Cuando te guste, pulsa **«game.yaml»** y copia o descarga el archivo: es tu
`game.yaml` entero, con los mapas nuevos. Detalles en
[editor.md](editor.md).

## 3b. …o cambia el mapa a mano

Abre `game.yaml` y busca `niveles:`. El mapa son caracteres:

```yaml
  - nombre: "BOSQUE"
    mapa: |
      ....................
      ..........ccc.......
      .........=====......
      ....................
      P....s............G.
      ####################
```

- `P` dónde empiezas (solo una)
- `#` suelo, `=` plataforma que se atraviesa desde abajo, `^` pinchos
- `G` la meta
- `s` una seta, `c` una moneda (mira `spawns:`)

Cambia lo que quieras y vuelve a lanzar `../ngplat probar`. Tarda menos de un
segundo.

Consejo: el salto del héroe por defecto sube **2 tiles** y cruza **3 tiles** de
hueco. Si haces un hueco de 4, no se puede pasar (o sube `salto:`).

## 4. Cambia el personaje

Los gráficos están en `graficos/`. `heroe.png` es una tira de 6 fotogramas de
16x16 píxeles:

| 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| quieto | correr | correr | correr | saltar | caer |

Ábrelo con cualquier editor de píxeles (Aseprite, Piskel, GIMP, Paint) y
dibuja encima. Reglas:

- **Máximo 15 colores** más el transparente.
- El tamaño del fotograma tiene que ser múltiplo de 16.
- Si añades fotogramas, cambia también las `animaciones` del `game.yaml`.

¿Quieres un héroe más alto? Haz los fotogramas de 16x32 y pon:

```yaml
jugador:
  frame: [16, 32]
  caja: [10, 30]
```

## 5. Ajusta cómo se siente

Son las opciones que más cambian el juego:

```yaml
jugador:
  velocidad: 1.6      # súbelo a 2.2 para un juego rápido
  salto: 4.3          # 5.2 salta mucho más alto
  gravedad: 0.28      # 0.20 = flotante, 0.40 = pesado
  doble_salto: si     # segundo salto en el aire
```

Cambia un valor, `../ngplat probar` y lo notas al instante.

## 6. Añade un enemigo nuevo

```yaml
enemigos:
  fantasma:
    sprite: graficos/enemigo.png
    comportamiento: perseguidor    # te sigue si te acercas
    velocidad: 0.7
    rango: 120
    puntos: 300

spawns:
  f: fantasma        # ahora puedes poner 'f' en los mapas
```

## 6b. Cambia el fondo

El proyecto viene con dos capas de parallax (`graficos/cielo.png` y
`graficos/arboles.png`). Son PNG normales que se repiten en horizontal:

```yaml
fondos:
  - nombre: cielo
    imagen: graficos/cielo.png
    velocidad: 0.2      # cuanto mas bajo, mas lejos parece
    y: 0
  - nombre: arboles
    imagen: graficos/arboles.png
    velocidad: 0.5
    y: 144
```

Pinta encima de esos PNG (15 colores por capa) o añade otra capa. Si un nivel
concreto quiere otras capas, se lo dices en el propio nivel con
`fondos: [cielo]`.

## 6c. Cambia la música

La música y los efectos también están en el `game.yaml`, escritos con notas:

```yaml
sonido:
  efectos:
    salto: {tipo: barrido, desde: 320, hasta: 900, duracion: 6}
    moneda: {notas: "mi6 sol6", velocidad: 3}
  musica:
    bosque:
      velocidad: 8
      pistas:
        - "do4 mi4 sol4 mi4 | fa4 la4 do5 la4"
        - "do3 -   do3 -    | fa3 -   fa3 -"
```

Cambia las notas y vuelve a lanzar `../ngplat probar`: el preview lo toca al
momento (con <kbd>M</kbd> silencias). La primera pista es la melodía y la
segunda el acompañamiento; el tercer canal del chip se queda para los efectos.

## 7. Añade un nivel

Copia el bloque de un nivel y cambia el mapa. Se juegan en orden:

```yaml
niveles:
  - nombre: "BOSQUE"
    mapa: |
      ...
  - nombre: "CUEVA"
    fondo: "#180c20"
    mapa: |
      ...
```

## 8. Haz la ROM

```bash
../ngplat compilar
cd build
make          # necesita ngdevkit instalado
make run      # arranca el emulador de ngdevkit
```

Si no tienes ngdevkit, `ngplat compilar` ya te ha dejado en `build/` todo el
proyecto en C y las ROMs gráficas: puedes compilarlo en otro ordenador que sí
lo tenga.

## Cuando algo falla

```bash
../ngplat comprobar
```

Te dice el problema, dónde está y cómo arreglarlo. Ejemplos:

```
error en niveles[1]: el mapa usa el simbolo '@' (fila 4, columna 12) y no esta en la leyenda
  pista: anadelo en 'tiles: leyenda:' o en 'spawns:' del nivel

error en jugador: el fotograma mide 12x12 y la Neo Geo dibuja sprites en bloques de 16x16
  pista: usa medidas multiplos de 16 (16x16, 16x32, 32x32...)
```
