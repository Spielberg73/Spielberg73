# El editor de niveles

El preview que abre `ngplat probar` trae un editor dentro. No hay que instalar
nada: es la misma página, con un botón.

```bash
ngplat probar          # abre el juego
```

Pulsa **<kbd>E</kbd>** o el botón **«editar el nivel»**. El juego se pausa y
aparecen la paleta y la barra de herramientas.

## Lo básico

| Acción | Cómo |
|---|---|
| Pintar | clic (o dedo) sobre el mapa; arrastra para pintar varios |
| Borrar | clic derecho, o elige el tile `vacío` |
| Elegir qué pintas | los botones de la paleta (tiles, enemigos, objetos, salida) |
| Mover la vista | herramienta ✋ y arrastra, o las flechas (<kbd>Shift</kbd> va más rápido) |
| Ir a otra parte | clic en el minimapa de abajo |
| Deshacer | <kbd>Ctrl</kbd>+<kbd>Z</kbd> o el botón «deshacer» |
| Probar lo editado | <kbd>Enter</kbd> o «probar el nivel» |
| Volver a editar | <kbd>E</kbd> |

La paleta se construye sola a partir de **tu** `game.yaml`: sale un botón por
cada símbolo de la leyenda (con su dibujo real) y otro por cada enemigo u
objeto que hayas definido en `spawns`.

## Reglas que vigila el editor

- **Solo puede haber una salida `P`**: al colocar una nueva, la anterior
  desaparece.
- Si el nivel se queda **sin salida o sin meta**, te lo dice debajo de la
  paleta. No te lo impide (a lo mejor estás a medias), pero te avisa.
- El nivel no puede ser más pequeño que una pantalla (20 × 14 tiles).

## Cambiar el tamaño del nivel

Los botones **+ ancho / − ancho / + alto / − alto** añaden o quitan columnas por
la derecha y filas por arriba, dejando la fila del suelo donde estaba.

## Llevarte los cambios

Pulsa **«game.yaml»**: aparece el archivo completo, ya con tus mapas.

- **«copiar al portapapeles»** y lo pegas en tu `game.yaml`.
- **«descargar game.yaml»** te lo baja. Si estás viendo el preview publicado en
  claude.ai, la descarga pasa por el visor y llega como `game.yaml.txt`: solo
  hay que renombrarlo.

Lo que se exporta es **todo el `game.yaml`**, no solo los mapas: se conservan la
física del jugador, los enemigos, las capas de fondo, el sonido y los
comentarios. El editor solo sustituye los bloques `mapa: |`.

> Lo que el editor **no** toca todavía: crear niveles nuevos, definir enemigos o
> cambiar la física. Eso sigue siendo un rato de escribir en el `game.yaml`,
> que para eso es un archivo de texto.

## Por qué esto es fiable

El editor trabaja siempre sobre el mapa en texto, igual que el archivo. Cuando
pulsas «probar el nivel», reconstruye los datos del nivel **con las mismas
cuentas que hace el compilador** (posición de la salida, cajas de los enemigos,
índices de tile). Y las pruebas del kit hacen el viaje completo: editan un
nivel, exportan el `game.yaml` y lo vuelven a compilar para comprobar que sigue
siendo válido y que no se ha perdido nada por el camino.
