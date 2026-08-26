# El editor

El preview que abre `ngplat probar` **es** el editor. No hay que instalar nada
ni cambiar de programa: pulsas <kbd>E</kbd> y el juego se pausa para que lo
edites; <kbd>Enter</kbd> y lo estás jugando otra vez.

```bash
ngplat probar          # abre el juego; pulsa E para editar
```

Todo lo que cambias sale al final en tu `game.yaml`, conservando comentarios,
orden y formato: el editor solo toca las líneas que has modificado.

---

## Mapa

La pestaña **mapa** es donde se dibuja.

| Herramienta | Tecla | Qué hace |
|---|---|---|
| lápiz | <kbd>1</kbd> | pinta casilla a casilla; arrastra para hacer trazos |
| rectángulo | <kbd>2</kbd> | arrastra y suelta; el botón derecho borra |
| relleno | <kbd>3</kbd> | llena toda la zona contigua, respetando las paredes |
| selección | <kbd>4</kbd> | marca un rectángulo para copiar, cortar, pegar o borrar |
| cuentagotas | <kbd>5</kbd> | coge el símbolo que hay bajo el cursor (o <kbd>Alt</kbd>+clic) |
| mover | <kbd>6</kbd> | arrastra la vista |

Otros atajos: <kbd>Ctrl</kbd>+<kbd>Z</kbd> deshacer, <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd>
rehacer, <kbd>Ctrl</kbd>+<kbd>C</kbd>/<kbd>X</kbd>/<kbd>V</kbd> copiar, cortar y
pegar, <kbd>Supr</kbd> borrar la selección, <kbd>G</kbd> rejilla, <kbd>H</kbd>
guías de pantalla, flechas para moverte (con <kbd>Shift</kbd> más rápido),
<kbd>Esc</kbd> quitar la selección.

Un **trazo entero cuenta como un solo paso de deshacer**, no uno por casilla.

La **paleta** se construye desde tu propio `game.yaml`: sale un botón por cada
símbolo de la leyenda (con su dibujo real) y otro por cada enemigo u objeto que
hayas definido en `spawns`, más la salida del jugador.

Debajo del lienzo hay un **minimapa**: enseña el nivel entero y el recuadro de
lo que estás viendo; haz clic para ir a cualquier parte. Las **guías** marcan
dónde cae cada pantalla de 320×224, que es lo que se ve de golpe en la consola.

También puedes **alejar y acercar** (0,5× / 1:1 / 2×) y cambiar el tamaño del
nivel con ± ancho y ± alto, que respetan la fila del suelo.

## Nivel

Nombre, color de fondo, música y qué capas de parallax usa. Y la gestión de
niveles: **nuevo** (nace con salida, meta y suelo, listo para jugar),
**duplicar**, **borrar** y **subir/bajar** para cambiar el orden.

## Juego y física

Título, autor, vidas, tiempo límite, la **máquina** para la que se compila
(Neo Geo, Mega Drive o Amiga) y todos los ajustes del jugador con
deslizadores: velocidad, salto, gravedad, aceleración, fricción, control en el
aire, corte del salto, caída máxima, rebote, coyote, buffer de salto, vida,
invulnerabilidad, doble salto y pisar enemigos.

Cada cambio se aplica **al momento**: pulsa <kbd>Enter</kbd> y lo pruebas. Debajo
te dice lo que consigue tu salto con esos números, por ejemplo:

> con estos ajustes el salto sube 31 px (1 casilla) y cruza 48 px (3 casillas)

Eso es lo que hay que mirar antes de dibujar un hueco.

La máquina se guarda en el `game.yaml` como cualquier otro ajuste, pero no
cambia el preview al vuelo: los colores que ves son los de la máquina con la
que se generó. Para verlo con otra, guarda el yaml y vuelve a lanzar
`ngplat probar --sistema <máquina>`.

## Enemigos y objetos

Cada enemigo definido en el `game.yaml` con su comportamiento (patrulla,
volador, perseguidor, saltarín, fijo), velocidad, vida, daño, puntos, si se
puede pisar, si gira en los bordes y los ajustes propios de cada
comportamiento. Los objetos, con su efecto, puntos y cantidad. Y el botón
**borrar**, que además limpia el mapa de sus apariciones.

### Crear uno nuevo

**«+ enemigo nuevo»** o **«+ objeto nuevo»** abre un formulario con todo lo que
hace falta:

- **nombre** y **símbolo** del mapa (te propone uno libre; no deja repetidos ni
  pisar un tile)
- **dibujo**: reaprovecha uno de los PNG que ya tiene el proyecto, o **dibújalo
  ahí mismo**
- **tamaño** del fotograma (16×16, 16×32, 32×16, 32×32), **cuántos fotogramas** y
  la **caja de colisión**
- comportamiento, velocidad, vida y puntos (o efecto y puntos, si es un objeto)

Al crearlo aparece en la paleta del mapa y lo puedes pintar y probar al momento.

Si eliges «dibujarlo aquí» sale un lienzo pequeño con lo justo para inventarse
un bicho. Para todo lo demás está la pestaña **dibujos**.

## Dibujos

Aquí se dibuja **cualquier cosa del proyecto**: el jugador, cada enemigo, cada
objeto, el escenario y las capas de fondo. La lista de la izquierda las tiene
todas; se pincha una y se abre con su propia paleta.

Dos cosas que no puede hacer un editor de píxeles normal, y que son la razón de
que este viva dentro del kit:

- **los colores son los de la máquina de destino.** El dibujo se carga desde el
  PNG ya pasado por el redondeo de la máquina, así que lo que ves en el lienzo
  es exactamente lo que se verá en la Neo Geo, el Amiga o donde sea. Y el
  contador de arriba a la derecha dice **cuántos colores llevas de los que
  caben**, en rojo si te pasas, antes de que te lo diga el compilador;
- **la animación corre a la velocidad de verdad.** La vista previa de la derecha
  reproduce la animación que elijas (`quieto`, `correr`, `saltar`...) con los
  fotogramas y la velocidad que tiene ese actor en el `game.yaml`, mientras
  dibujas.

**Herramientas**: lápiz, borrador, línea, rectángulo (hueco o lleno), elipse
(hueca o llena), relleno por zonas, cuentagotas y mover un trozo. Todo con
deshacer y rehacer.

**Del fotograma**: espejo, volteo, girar (si es cuadrado), limpiar, duplicar (se
copia del anterior, que es como se animan las cosas) y quitar.

**Para ver bien**: zoom, rejilla de píxel, marcas de fotograma —el activo va en
amarillo— y **papel cebolla**, que enseña el fotograma anterior en fantasma
debajo del que estás dibujando.

Un sprite se abre a tamaño grande, para dibujar píxel a píxel; una capa de fondo
entera se abre como quepa, para verla de un vistazo.

**Guardar.** Con `ngplat probar` en marcha, «guardar» deja el PNG en su sitio
dentro del proyecto y el preview lo usa al momento: dibujas, guardas y lo ves en
el juego sin salir del navegador. Si has abierto el `preview.html` a pelo
(`file://`) no hay con quien hablar y el botón lo descarga para que lo pongas a
mano.

## Revisar

Una lista en vivo de lo que está mal en el nivel, con clic para ir al sitio:

- falta la salida `P` o hay más de una
- no hay meta: el nivel no se puede terminar
- un enemigo colocado en el aire, que se caerá al empezar
- un hueco más ancho de lo que cruza el salto (con **tus** números)
- más de 64 enemigos y objetos, o un nivel más pequeño que una pantalla

Y el botón **«¿se puede terminar?»**: lanza un bot que juega el nivel de
principio a fin igual que lo haría alguien la primera vez (andar y saltar
cuando ve algo). Si no llega, te dice por qué y te lleva al punto donde se
quedó. Es el mismo bot que usan las pruebas del kit.

## game.yaml

El archivo completo con tus cambios. **Copiar al portapapeles** o **descargar**.

Si estás en el preview publicado en claude.ai, la descarga pasa por el visor y
llega como `game.yaml.txt`: solo hay que renombrarlo.

## Compilar

La pestaña **compilar** construye el juego sin salir del editor: eliges máquina
y el botón guarda tu `game.yaml` en el proyecto y compila, dejando el registro
de lo que ha pasado ahí mismo.

El botón dice lo que va a salir, porque no todas las máquinas hacen lo mismo:

| Máquina | Sale |
|---|---|
| Neo Geo | **la ROM** — el romset P1/C1/C2/S1/M1 |
| Mega Drive | **el cartucho** — un `.bin` de 128 KB |
| Amiga | **el disquete** — un `.adf` de 880 KB que arranca solo |

Para que funcione, el preview lo tiene que estar sirviendo el propio `ngplat`,
porque una página web no puede compilar nada. Eso es lo que hace `ngplat probar`
por defecto:

```bash
ngplat probar          # abre el navegador y se queda sirviendo; Ctrl+C para parar
```

Si abres el `preview.html` a mano (doble clic, `--no-servidor`, o el preview
publicado en claude.ai) el botón sale apagado y te dice esto mismo: ahí hay que
exportar el `game.yaml` desde la pestaña de al lado y compilar con
`ngplat compilar --make`.

Detalles que conviene saber:

- **Guarda de verdad.** El `game.yaml` del proyecto se sobrescribe con lo que
  tengas en el editor, dejando el anterior en `game.yaml.bak`.
- **Si lo que mandas no se puede leer, no se guarda.** El archivo vuelve a como
  estaba y el registro dice qué línea falla.
- **Si no hay compilador de 68000**, el proyecto se genera igual (código C,
  ROMs de gráficos, ROM de sonido) y el registro te dice qué falta instalar.
- El servidor escucha **solo en 127.0.0.1** y exige una clave que se genera al
  arrancar y que va en la dirección que abre el navegador. Sin eso, cualquier
  otra página que tuvieras abierta podría escribir en tu `game.yaml` y lanzar un
  `make`: los navegadores dejan que cualquier sitio hable con localhost.

## No se pierde nada

El editor **guarda solo** en el navegador cada vez que tocas algo. Si cierras
sin exportar, la próxima vez que abras el preview te ofrece recuperar lo que
estabas haciendo. El botón «olvidar cambios guardados» lo borra.

## Por qué puedes fiarte

- El editor trabaja sobre el mapa en texto, igual que el archivo.
- Al pulsar «probar el nivel» reconstruye los datos **con las mismas cuentas que
  el compilador** (posición de la salida, cajas de los enemigos, índices de
  tile), así que lo que juegas es lo que se compila.
- Al exportar, cada opción se escribe con el nombre que ya tenía en tu archivo
  (en castellano o en inglés) y solo si la has cambiado. Hay una prueba que
  comprueba, opción por opción, que todos esos nombres los entiende el lector.
- Las pruebas del kit hacen el viaje entero: editan mapas, física, niveles y
  crean enemigos y objetos en el editor, exportan el `game.yaml`, lo vuelven a
  compilar y comprueban que no se ha perdido ni un comentario. La prueba de
  navegador llega a dibujar un enemigo con el ratón, colocarlo, jugarlo y
  comprobar que su PNG queda listo para guardar.
