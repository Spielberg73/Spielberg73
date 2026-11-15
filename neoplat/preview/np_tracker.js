/* np_tracker.js - la rejilla del tracker, sin pantalla ni sonido.
 *
 * Aqui no hay ni una linea de interfaz: solo las cuentas de pasar de las
 * cadenas de `pistas:` a una rejilla de celdas y de la rejilla otra vez a las
 * cadenas. Esta aparte justamente para poder probarlo, que es la mitad del
 * trabajo en algo asi: una rejilla que al guardar te cambia la cancion no
 * sirve de nada, y eso no se ve mirando la pantalla.
 *
 * **El tracker es una vista, no un formato nuevo.** La musica del kit son dos
 * lineas de texto -"do4 mi4 sol4 | fa4 ..."- y eso no cambia: la rejilla se
 * saca de ahi y vuelve ahi. Por eso el tracker no toca el motor, ni el
 * compilador, ni el chip de ninguna maquina: lo que se escribe en la rejilla
 * compila en las ocho igual que si lo hubieras escrito a mano, porque es lo
 * mismo.
 *
 * Una celda es una de estas cuatro cosas:
 *
 *   {tipo: "nota", nota: "do4"}   una nota; `nota` es el texto tal cual venia
 *   {tipo: "silencio"}            un '-'
 *   {tipo: "sigue"}               la nota de arriba, que dura mas de un paso
 *   {tipo: "fuera"}               aqui esta pista ya se ha acabado
 *
 * "sigue" es lo que en el texto es `do4:3`: la nota ocupa tres pasos, asi que
 * en la rejilla son tres filas -una nota y dos "sigue"-, que es como se ve en
 * cualquier tracker y como hay que verlo para saber donde cae cada cosa.
 *
 * Y "fuera" existe porque las dos pistas pueden medir distinto, y rellenar la
 * corta con silencios **cambiaria la cancion**. Una pista de 16 pasos sigue
 * teniendo 16 pasos despues de pasar por aqui, aunque la otra tenga 32.
 */
(function (root) {
  "use strict";

  /* Para separar el nombre de la nota del `:n`. Lo de si la nota **vale** no
   * se decide aqui: eso lo dice np_sonido.js, por lo que hay escrito en
   * `valeComoNota`. */
  var NOTA_RE = /^(do|re|mi|fa|sol|la|si|[a-g])([#b]?)(-?\d)?$/i;
  var SILENCIOS = ["-", "_", "."];
  var COMPAS_POR_DEFECTO = 4;

  /* Las notas de una octava, para escribir con el teclado. El orden es el de
   * las teclas de un piano, que es como se tocan. */
  var NOMBRES = ["do", "do#", "re", "re#", "mi", "fa",
                 "fa#", "sol", "sol#", "la", "la#", "si"];

  /* Las teclas con las que se escribe, en dos filas como en los trackers de
   * siempre: la de abajo es la octava que marca el editor y la de arriba la
   * siguiente. Son las letras de un teclado espanol en las mismas posiciones
   * que tendrian en uno ingles: lo que importa es donde esta la tecla. */
  var TECLAS = {
    z: 0, s: 1, x: 2, d: 3, c: 4, v: 5, g: 6, b: 7, h: 8, n: 9, j: 10, m: 11,
    q: 12, "2": 13, w: 14, "3": 15, e: 16, r: 17, "5": 18, t: 19,
    "6": 20, y: 21, "7": 22, u: 23
  };

  function esSilencio(token) {
    return SILENCIOS.indexOf(token) !== -1;
  }

  /* El compilador de verdad. Se busca cada vez y no al cargar porque en el
   * editor los dos ficheros se meten en la pagina en orden y conviene no
   * depender de cual gana. */
  function _sonido() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./np_sonido.js");
    }
    return root.NPSonido;
  }

  /**
   * Si una nota se puede escribir en la rejilla.
   *
   * Y esto **no** es "si esta bien escrita": es si el compilador la acepta. No
   * basta con que `do0` se entienda, porque `do0` son 16 Hz y ninguna de estas
   * maquinas baja ahi, asi que sonido.py la rechaza. Una rejilla que te deja
   * escribir una nota que luego no compila es una trampa: te enteras media
   * hora despues, al construir la ROM.
   *
   * Por eso se le pregunta a np_sonido.js, que es el gemelo de sonido.py, en
   * vez de tener aqui otra copia de los limites del chip. Hay una prueba que
   * exige que los dos digan lo mismo nota por nota.
   */
  function valeComoNota(texto) {
    var limpio = String(texto == null ? "" : texto).trim();
    if (!NOTA_RE.test(limpio)) return false;
    var sonido = _sonido();
    if (!sonido) return true;          // sin el compilador, lo que se entienda
    try {
      sonido.notas(limpio, 1, 15);
      return true;
    } catch (e) {
      return false;
    }
  }

  /** "do", 4 -> "do4". Para lo que se escribe con el teclado. */
  function nombreDeNota(semitono, octava) {
    var dentro = ((semitono % 12) + 12) % 12;
    var salto = Math.floor(semitono / 12);
    return NOMBRES[dentro] + String(octava + salto);
  }

  function _tokens(texto) {
    /* '|' separa compases y puede venir pegado a una nota, igual que en
     * sonido.py: "do4|mi4" son dos notas y una barra. */
    return String(texto == null ? "" : texto)
      .replace(/\|/g, " | ")
      .split(/\s+/)
      .filter(function (t) { return t.length > 0; });
  }

  /** Una cadena de notas -> {celdas, barras, largo, error}. */
  function pistaARejilla(texto) {
    var celdas = [];
    var barras = [];
    var error = "";
    _tokens(texto).forEach(function (token) {
      if (token === "|") {
        if (celdas.length > 0 && barras.indexOf(celdas.length) === -1) {
          barras.push(celdas.length);
        }
        return;
      }
      if (esSilencio(token)) {
        celdas.push({ tipo: "silencio" });
        return;
      }
      var partido = /^(.*?)(?::(\d+))?$/.exec(token);
      var nota = partido[1];
      var largo = Math.max(1, Number(partido[2] || 1));
      if (!valeComoNota(nota)) {
        if (!error) error = "no entiendo la nota '" + token + "'";
        return;
      }
      celdas.push({ tipo: "nota", nota: nota });
      for (var i = 1; i < largo; i++) celdas.push({ tipo: "sigue" });
    });
    return {
      celdas: celdas, barras: barras, largo: celdas.length, error: error,
      /* El texto tal cual venia, y si se ha tocado. Con esto, guardar despues
       * de editar **solo** una pista deja la otra byte a byte como estaba: un
       * tracker que te reescribe las dos lineas cada vez que guardas te llena
       * el game.yaml de cambios que no has hecho. */
      original: String(texto == null ? "" : texto),
      tocada: false
    };
  }

  function _compasRegular(pistas) {
    /* El compas que se usa para las filas nuevas: el de la cancion, si todos
     * los compases miden lo mismo. Si no miden lo mismo no se inventa ninguno
     * -hay musica que va asi- y las barras que ya habia se respetan tal cual. */
    var medidas = [];
    pistas.forEach(function (p) {
      var antes = 0;
      p.barras.forEach(function (b) { medidas.push(b - antes); antes = b; });
    });
    if (!medidas.length) return 0;
    for (var i = 1; i < medidas.length; i++) {
      if (medidas[i] !== medidas[0]) return 0;
    }
    return medidas[0];
  }

  /**
   * Las pistas de una cancion -> la rejilla entera.
   *
   * `filas` es la pista mas larga: es lo que hay que dibujar. Cada pista
   * conserva su propio `largo`, y lo que pase de ahi son celdas "fuera".
   */
  function aRejilla(fuente) {
    var textos = (fuente && fuente.pistas) || [];
    var pistas = textos.map(pistaARejilla);
    var filas = pistas.reduce(function (maximo, p) {
      return Math.max(maximo, p.largo);
    }, 0);
    var error = "";
    pistas.forEach(function (p, i) {
      if (p.error && !error) error = "pista " + (i + 1) + ": " + p.error;
    });
    return {
      filas: filas,
      compas: _compasRegular(pistas),
      pistas: pistas,
      error: error
    };
  }

  /** La celda que toca, o "fuera" si esa pista ya se ha acabado. */
  function celda(rejilla, pista, fila) {
    var p = rejilla.pistas[pista];
    if (!p || fila < 0 || fila >= p.largo) return { tipo: "fuera" };
    return p.celdas[fila];
  }

  function _tocaBarra(p, paso, compas) {
    if (paso <= 0) return false;
    if (p.barras.indexOf(paso) !== -1) return true;
    if (!compas) return false;
    /* Pasada la ultima barra que traia la cancion, se sigue compasando sola:
     * asi las filas nuevas salen con sus barras y no se queda la mitad de
     * abajo sin separar. */
    var ultima = p.barras.length ? p.barras[p.barras.length - 1] : 0;
    return paso > ultima && (paso - ultima) % compas === 0;
  }

  /** Una pista de la rejilla -> la cadena de notas de siempre. */
  function pistaATexto(p, compas) {
    var trozos = [];
    var paso = 0;
    while (paso < p.largo) {
      if (_tocaBarra(p, paso, compas)) trozos.push("|");
      var actual = p.celdas[paso];
      if (!actual || actual.tipo === "silencio" || actual.tipo === "sigue") {
        /* Un "sigue" sin nota delante -se ha borrado la nota y han quedado
         * sus colas- es un silencio: no hay nada que alargar. */
        trozos.push("-");
        paso += 1;
        continue;
      }
      var largo = 1;
      while (paso + largo < p.largo &&
             p.celdas[paso + largo] &&
             p.celdas[paso + largo].tipo === "sigue") {
        largo += 1;
      }
      /* La nota se lleva por delante las barras que le caigan dentro, y es a
       * proposito: una barra es solo una raya para leer, pero cortar aqui la
       * nota en dos **cambiaria la cancion** -lo que suena no es una nota
       * larga, son dos notas repetidas-, y una nota larga a caballo entre dos
       * compases es de lo mas normal del mundo. */
      trozos.push(largo > 1 ? actual.nota + ":" + largo : actual.nota);
      paso += largo;
    }
    /* En columnas, que es como se lee un tracker: todas las notas ocupan lo
     * mismo y se ve de un vistazo que cae con que en la otra pista. */
    var ancho = trozos.reduce(function (maximo, token) {
      return token === "|" ? maximo : Math.max(maximo, token.length);
    }, 1);
    return trozos.map(function (token, i) {
      if (token === "|" || i === trozos.length - 1) return token;
      while (token.length < ancho) token += " ";
      return token;
    }).join(" ").replace(/\s+$/, "");
  }

  /** La rejilla entera -> las cadenas que van al game.yaml. */
  function aPistas(rejilla) {
    return rejilla.pistas.map(function (p) {
      return p.tocada ? pistaATexto(p, rejilla.compas) : p.original;
    });
  }

  function _asegurar(rejilla, pista, fila) {
    var p = rejilla.pistas[pista];
    if (!p) return null;
    /* Escribir en la fila 20 de una pista que mide 16 la alarga, y lo que
     * queda en medio son silencios: es lo que uno espera al pinchar ahi. */
    while (p.largo <= fila) {
      p.celdas.push({ tipo: "silencio" });
      p.largo += 1;
      p.tocada = true;
    }
    if (rejilla.filas < p.largo) rejilla.filas = p.largo;
    return p;
  }

  /** Pone una nota. Devuelve si ha podido. */
  function ponerNota(rejilla, pista, fila, nota) {
    if (!valeComoNota(nota)) return false;
    var p = _asegurar(rejilla, pista, fila);
    if (!p) return false;
    p.celdas[fila] = { tipo: "nota", nota: String(nota).trim() };
    p.tocada = true;
    return true;
  }

  /** Pone un silencio. */
  function ponerSilencio(rejilla, pista, fila) {
    var p = _asegurar(rejilla, pista, fila);
    if (!p) return false;
    p.celdas[fila] = { tipo: "silencio" };
    p.tocada = true;
    return true;
  }

  /** Alarga la nota de arriba hasta aqui. */
  function ponerSigue(rejilla, pista, fila) {
    if (fila <= 0) return false;
    var p = _asegurar(rejilla, pista, fila);
    if (!p) return false;
    p.celdas[fila] = { tipo: "sigue" };
    p.tocada = true;
    return true;
  }

  /**
   * Borra una celda **del todo**: la fila deja de existir en esa pista.
   *
   * No es lo mismo que poner un silencio. Poner un silencio deja el hueco y
   * la cancion dura lo mismo; borrar la ultima fila acorta la pista, que es lo
   * que hace falta para deshacer un "me he pasado de filas".
   */
  function quitarFila(rejilla, pista, fila) {
    var p = rejilla.pistas[pista];
    if (!p || fila < 0 || fila >= p.largo) return false;
    p.celdas.splice(fila, 1);
    p.largo -= 1;
    p.tocada = true;
    p.barras = p.barras.map(function (b) { return b > fila ? b - 1 : b; })
      .filter(function (b) { return b > 0 && b < p.largo; });
    rejilla.filas = rejilla.pistas.reduce(function (maximo, otra) {
      return Math.max(maximo, otra.largo);
    }, 0);
    return true;
  }

  /** Mete una fila vacia en todas las pistas que lleguen hasta ahi. */
  function meterFila(rejilla, fila) {
    rejilla.pistas.forEach(function (p) {
      if (fila > p.largo) return;
      p.celdas.splice(fila, 0, { tipo: "silencio" });
      p.largo += 1;
      p.tocada = true;
      p.barras = p.barras.map(function (b) { return b >= fila ? b + 1 : b; });
    });
    rejilla.filas = rejilla.pistas.reduce(function (maximo, p) {
      return Math.max(maximo, p.largo);
    }, 0);
    return true;
  }

  /** Sube o baja de semitono en semitono lo que haya en la rejilla. */
  function transportar(rejilla, pista, desde, hasta, semitonos) {
    var p = rejilla.pistas[pista];
    if (!p) return false;
    var hecho = false;
    for (var fila = desde; fila <= hasta && fila < p.largo; fila++) {
      var c = p.celdas[fila];
      if (!c || c.tipo !== "nota") continue;
      var partes = NOTA_RE.exec(c.nota);
      if (!partes) continue;
      var semitono = { do: 0, c: 0, re: 2, d: 2, mi: 4, e: 4, fa: 5, f: 5,
                       sol: 7, g: 7, la: 9, a: 9, si: 11, b: 11 }[
        partes[1].toLowerCase()];
      if (partes[2] === "#") semitono += 1;
      else if (partes[2] === "b") semitono -= 1;
      var octava = partes[3] === undefined ? 4 : Number(partes[3]);
      var total = octava * 12 + semitono + semitonos;
      var octavaNueva = Math.floor(total / 12);
      var nueva = nombreDeNota(((total % 12) + 12) % 12, octavaNueva);
      /* Lo que no quepa en el chip no se escribe: bajar cuatro octavas deja
       * notas de 16 Hz que no compilan, y es mejor que esa nota se quede
       * donde esta que dejar la cancion sin construir. */
      if (octavaNueva < 0 || octavaNueva > 9 || !valeComoNota(nueva)) continue;
      p.celdas[fila] = { tipo: "nota", nota: nueva };
      p.tocada = true;
      hecho = true;
    }
    return hecho;
  }

  var api = {
    aRejilla: aRejilla, aPistas: aPistas,
    pistaARejilla: pistaARejilla, pistaATexto: pistaATexto,
    celda: celda,
    ponerNota: ponerNota, ponerSilencio: ponerSilencio, ponerSigue: ponerSigue,
    quitarFila: quitarFila, meterFila: meterFila, transportar: transportar,
    valeComoNota: valeComoNota, nombreDeNota: nombreDeNota,
    TECLAS: TECLAS, NOMBRES: NOMBRES,
    COMPAS_POR_DEFECTO: COMPAS_POR_DEFECTO
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NPTracker = api;
})(typeof window !== "undefined" ? window : this);
