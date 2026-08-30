/* np_yaml.js - retoques quirurgicos sobre el texto del game.yaml.
 *
 * El editor no reescribe el archivo entero: lo modifica por dentro, linea a
 * linea, para que se conserven tal cual los comentarios, el orden y el estilo
 * de quien lo escribio. Solo cambia lo que has tocado.
 *
 * Trabaja sobre texto, no sobre un arbol: asi no hace falta un analizador de
 * YAML completo en el navegador y no hay forma de que "reordene" el archivo.
 */
(function (root) {
  "use strict";

  function sangriaDe(linea) {
    var m = /^[ ]*/.exec(linea);
    return m[0].length;
  }

  /* Solo cuentan como hueco las lineas en blanco. Ojo: una fila de mapa llena
     de suelo ("######") empieza por '#' y parece un comentario, asi que no se
     puede mirar el '#' para decidir. Los comentarios de verdad se descartan
     solos: no encajan como "clave: valor". */
  function esHueco(linea) {
    return linea.trim() === "";
  }

  /** Separa "clave: valor  # comentario" respetando comillas. */
  function partirLinea(linea) {
    var m = /^([ ]*)([^:#]+):(.*)$/.exec(linea);
    if (!m) return null;
    var resto = m[3];
    var comentario = "";
    var comilla = "";
    for (var i = 0; i < resto.length; i++) {
      var ch = resto[i];
      if (comilla) {
        if (ch === comilla) comilla = "";
        continue;
      }
      if (ch === '"' || ch === "'") { comilla = ch; continue; }
      if (ch === "#" && (i === 0 || /\s/.test(resto[i - 1]))) {
        comentario = resto.substring(i);
        resto = resto.substring(0, i);
        break;
      }
    }
    return {
      sangria: m[1],
      clave: m[2].trim(),
      valor: resto.trim(),
      espacios: /\s*$/.exec(resto)[0],
      comentario: comentario
    };
  }

  function Yaml(texto) {
    this.lineas = String(texto).split("\n");
  }

  /* --------------------------------------------------------- busquedas */

  /** Rango [inicio, fin) del contenido de una seccion de primer nivel. */
  Yaml.prototype.seccion = function (alias, desde, hasta, sangriaClave) {
    desde = desde || 0;
    hasta = hasta === undefined ? this.lineas.length : hasta;
    for (var i = desde; i < hasta; i++) {
      var linea = this.lineas[i];
      if (esHueco(linea)) continue;
      var partes = partirLinea(linea);
      if (!partes) continue;
      if (sangriaClave !== undefined && partes.sangria.length !== sangriaClave) continue;
      if (alias.indexOf(partes.clave) < 0) continue;
      var sangria = partes.sangria.length;
      var fin = i + 1;
      while (fin < hasta) {
        var siguiente = this.lineas[fin];
        if (!esHueco(siguiente) && sangriaDe(siguiente) <= sangria) break;
        fin++;
      }
      return { clave: i, inicio: i + 1, fin: fin, sangria: sangria, nombre: partes.clave };
    }
    return null;
  };

  /** Sangria que usan los hijos directos de una seccion. */
  Yaml.prototype.sangriaHijos = function (rango) {
    for (var i = rango.inicio; i < rango.fin; i++) {
      var linea = this.lineas[i];
      if (esHueco(linea)) continue;
      var s = sangriaDe(linea);
      if (s > rango.sangria) return s;
    }
    return rango.sangria + 2;
  };

  /** Busca una clave entre los hijos directos de un rango. */
  Yaml.prototype.clave = function (rango, alias) {
    var sangria = this.sangriaHijos(rango);
    for (var i = rango.inicio; i < rango.fin; i++) {
      var linea = this.lineas[i];
      if (esHueco(linea)) continue;
      var partes = partirLinea(linea);
      if (!partes) continue;
      if (partes.sangria.length !== sangria) continue;
      if (alias.indexOf(partes.clave) >= 0) return { linea: i, partes: partes };
    }
    return null;
  };

  /* ------------------------------------------------------------ cambios */

  /** Pone (o anade) `clave: valor` dentro de un rango. */
  Yaml.prototype.ponerValor = function (rango, alias, valor) {
    if (!rango) return false;
    var encontrada = this.clave(rango, alias);
    if (encontrada) {
      var p = encontrada.partes;
      var separacion = p.espacios || (p.comentario ? " " : "");
      this.lineas[encontrada.linea] =
        p.sangria + p.clave + ": " + valor + separacion + p.comentario;
      return true;
    }
    var sangria = this.sangriaHijos(rango);
    var destino = rango.fin;
    while (destino > rango.inicio && esHueco(this.lineas[destino - 1])) destino--;
    this.lineas.splice(destino, 0,
      Array(sangria + 1).join(" ") + alias[0] + ": " + valor);
    return true;
  };

  /**
   * Igual que `ponerValor`, pero dejando la clave en **una sola linea**.
   *
   * Hace falta para las animaciones: se escriben en linea
   * (`correr: {frames: [1, 2], velocidad: 6}`) pero el usuario ha podido
   * escribirlas como un bloque de varias lineas. Si se le pusiera el valor a
   * la clave sin mas, los hijos del bloque se quedarian sueltos debajo y el
   * yaml saldria roto.
   */
  Yaml.prototype.ponerValorPlano = function (rango, alias, valor) {
    if (!rango) return false;
    var encontrada = this.clave(rango, alias);
    if (encontrada && !encontrada.partes.valor) {
      var sangria = encontrada.partes.sangria.length;
      var fin = encontrada.linea + 1;
      while (fin < this.lineas.length) {
        var linea = this.lineas[fin];
        if (esHueco(linea) || sangriaDe(linea) <= sangria) break;
        fin++;
      }
      if (fin > encontrada.linea + 1) {
        this.lineas.splice(encontrada.linea + 1, fin - encontrada.linea - 1);
        rango.fin -= fin - encontrada.linea - 1;
      }
    }
    return this.ponerValor(rango, alias, valor);
  };

  /** Busca una subseccion dentro de un rango y, si no esta, la crea vacia. */
  Yaml.prototype.asegurarSubseccion = function (rango, alias) {
    if (!rango) return null;
    var dentro = this.seccion(alias, rango.inicio, rango.fin,
                              this.sangriaHijos(rango));
    if (dentro) return dentro;
    var sangria = this.sangriaHijos(rango);
    var destino = rango.fin;
    while (destino > rango.inicio && esHueco(this.lineas[destino - 1])) destino--;
    this.lineas.splice(destino, 0, Array(sangria + 1).join(" ") + alias[0] + ":");
    return { clave: destino, inicio: destino + 1, fin: destino + 1,
             sangria: sangria, nombre: alias[0] };
  };

  Yaml.prototype.quitarClave = function (rango, alias) {
    var encontrada = this.clave(rango, alias);
    if (!encontrada) return false;
    this.lineas.splice(encontrada.linea, 1);
    return true;
  };

  /* ------------------------------------------ anadir cosas nuevas */

  /**
   * Anade lineas al final de una seccion (por ejemplo, un enemigo nuevo
   * dentro de 'enemigos:'). Si la seccion no existe, la crea justo antes de
   * `antesDe` (normalmente 'niveles:', que va al final del archivo).
   */
  Yaml.prototype.anadirEnSeccion = function (alias, lineas, antesDe) {
    var rango = this.seccion(alias, 0, this.lineas.length, 0);
    if (rango) {
      var destino = rango.fin;
      while (destino > rango.inicio && esHueco(this.lineas[destino - 1])) destino--;
      this.lineas.splice.apply(this.lineas, [destino, 0].concat(lineas));
      return true;
    }
    var referencia = antesDe ? this.seccion(antesDe, 0, this.lineas.length, 0) : null;
    var posicion = referencia ? referencia.clave : this.lineas.length;
    var bloque = [alias[0] + ":"].concat(lineas, [""]);
    this.lineas.splice.apply(this.lineas, [posicion, 0].concat(bloque));
    return true;
  };

  /** ¿Existe ya esta clave dentro de una seccion de primer nivel? */
  Yaml.prototype.tieneClaveEn = function (alias, nombre) {
    var rango = this.seccion(alias, 0, this.lineas.length, 0);
    if (!rango) return false;
    return !!this.clave(rango, [nombre]);
  };

  /** Borra una subseccion entera (un enemigo, un objeto...). */
  Yaml.prototype.borrarSubseccion = function (alias, nombre) {
    var rango = this.seccion(alias, 0, this.lineas.length, 0);
    if (!rango) return false;
    var sub = this.seccion([nombre], rango.inicio, rango.fin);
    if (!sub) return false;
    this.lineas.splice(sub.clave, sub.fin - sub.clave);
    return true;
  };

  /* -------------------------------------------------------- los niveles */

  /** Rangos de cada nivel dentro de 'niveles:'. */
  Yaml.prototype.niveles = function () {
    var seccion = this.seccion(["niveles", "levels"], 0, this.lineas.length, 0);
    if (!seccion) return [];
    var lista = [];
    var sangriaItem = null;
    for (var i = seccion.inicio; i < seccion.fin; i++) {
      var linea = this.lineas[i];
      if (esHueco(linea)) continue;
      var s = sangriaDe(linea);
      if (/^\s*-\s/.test(linea) && (sangriaItem === null || s === sangriaItem)) {
        sangriaItem = s;
        if (lista.length) lista[lista.length - 1].fin = i;
        lista.push({ clave: i, inicio: i, fin: seccion.fin, sangria: s });
      }
    }
    // el contenido de un nivel empieza en su propia linea del guion
    lista.forEach(function (nivel) {
      nivel.inicio = nivel.clave;
      while (nivel.fin > nivel.inicio && esHueco(this.lineas[nivel.fin - 1])) nivel.fin--;
    }, this);
    this._seccionNiveles = seccion;
    return lista;
  };

  /** Los hijos de un nivel van sangrados dos espacios tras el guion. */
  Yaml.prototype.sangriaHijosNivel = function (nivel) {
    for (var i = nivel.inicio + 1; i < nivel.fin; i++) {
      var linea = this.lineas[i];
      if (esHueco(linea)) continue;
      return sangriaDe(linea);
    }
    return nivel.sangria + 2;
  };

  /** Rango utilizable con ponerValor() para un nivel concreto. */
  Yaml.prototype.rangoNivel = function (indice) {
    var niveles = this.niveles();
    var nivel = niveles[indice];
    if (!nivel) return null;
    var sangria = this.sangriaHijosNivel(nivel);
    // la primera clave va pegada al guion ("- nombre: X"): se trata aparte
    return {
      clave: nivel.clave, inicio: nivel.inicio, fin: nivel.fin,
      sangria: sangria - 2, _guion: nivel.clave, _sangriaHijos: sangria
    };
  };

  Yaml.prototype.ponerValorNivel = function (indice, alias, valor) {
    var niveles = this.niveles();
    var nivel = niveles[indice];
    if (!nivel) return false;
    var sangria = this.sangriaHijosNivel(nivel);
    // ¿esta en la linea del guion?
    var guion = /^(\s*-\s+)(.*)$/.exec(this.lineas[nivel.clave]);
    if (guion) {
      var partes = partirLinea(guion[1].replace(/-/g, " ") + guion[2]);
      if (partes && alias.indexOf(partes.clave) >= 0) {
        var separacion = partes.espacios || (partes.comentario ? " " : "");
        this.lineas[nivel.clave] =
          guion[1] + partes.clave + ": " + valor + separacion + partes.comentario;
        return true;
      }
    }
    var rango = { inicio: nivel.clave + 1, fin: nivel.fin, sangria: sangria - 2 };
    var encontrada = this.clave(rango, alias);
    if (encontrada) {
      var p = encontrada.partes;
      var sep = p.espacios || (p.comentario ? " " : "");
      this.lineas[encontrada.linea] = p.sangria + p.clave + ": " + valor + sep + p.comentario;
      return true;
    }
    // se inserta justo antes del mapa, que siempre va al final del nivel
    var destino = nivel.fin;
    for (var i = nivel.clave + 1; i < nivel.fin; i++) {
      var partesMapa = partirLinea(this.lineas[i]);
      if (partesMapa && ["mapa", "map", "tilemap"].indexOf(partesMapa.clave) >= 0) {
        destino = i;
        break;
      }
    }
    this.lineas.splice(destino, 0, Array(sangria + 1).join(" ") + alias[0] + ": " + valor);
    return true;
  };

  /** Sustituye las filas del mapa de un nivel. */
  Yaml.prototype.ponerMapa = function (indice, filas) {
    var niveles = this.niveles();
    var nivel = niveles[indice];
    if (!nivel) return false;
    for (var i = nivel.inicio; i < nivel.fin; i++) {
      var partes = partirLinea(this.lineas[i]);
      if (!partes || ["mapa", "map", "tilemap"].indexOf(partes.clave) < 0) continue;
      if (partes.valor.charAt(0) !== "|") continue;
      var sangriaClave = partes.sangria.length;
      var fin = i + 1;
      var sangriaBloque = null;
      while (fin < this.lineas.length) {
        var linea = this.lineas[fin];
        if (esHueco(linea)) {
          var k = fin + 1;
          while (k < this.lineas.length && esHueco(this.lineas[k])) k++;
          if (k >= this.lineas.length) break;
          if (sangriaBloque !== null && sangriaDe(this.lineas[k]) < sangriaBloque) break;
          fin++;
          continue;
        }
        var s = sangriaDe(linea);
        if (s <= sangriaClave) break;
        if (sangriaBloque === null) sangriaBloque = s;
        fin++;
      }
      var relleno = Array((sangriaBloque === null ? sangriaClave + 2 : sangriaBloque) + 1).join(" ");
      var nuevas = filas.map(function (fila) { return relleno + fila; });
      this.lineas.splice.apply(this.lineas, [i + 1, fin - (i + 1)].concat(nuevas));
      return true;
    }
    return false;
  };

  /** Texto completo de un nivel (para duplicarlo o moverlo). */
  Yaml.prototype.textoNivel = function (indice) {
    var nivel = this.niveles()[indice];
    if (!nivel) return "";
    return this.lineas.slice(nivel.inicio, nivel.fin).join("\n");
  };

  Yaml.prototype.insertarNivel = function (indice, texto) {
    var niveles = this.niveles();
    var lineas = texto.split("\n");
    if (!niveles.length) {
      var seccion = this.seccion(["niveles", "levels"], 0, this.lineas.length, 0);
      if (!seccion) return false;
      this.lineas.splice.apply(this.lineas, [seccion.fin, 0].concat(lineas));
      return true;
    }
    var destino = indice >= niveles.length
      ? niveles[niveles.length - 1].fin
      : niveles[indice].inicio;
    this.lineas.splice.apply(this.lineas, [destino, 0].concat(lineas));
    return true;
  };

  Yaml.prototype.borrarNivel = function (indice) {
    var niveles = this.niveles();
    var nivel = niveles[indice];
    if (!nivel || niveles.length <= 1) return false;
    this.lineas.splice(nivel.inicio, nivel.fin - nivel.inicio);
    return true;
  };

  Yaml.prototype.texto = function () {
    return this.lineas.join("\n");
  };

  /* --------------------------------------------------------- utilidades */

  function numero(valor, decimales) {
    var n = Number(valor);
    if (!isFinite(n)) return "0";
    if (decimales === 0 || n === Math.round(n) && decimales === undefined) {
      return String(Math.round(n));
    }
    var texto = n.toFixed(decimales === undefined ? 2 : decimales);
    return texto.replace(/0+$/, "").replace(/\.$/, "");
  }

  function siNo(valor) { return valor ? "si" : "no"; }

  function entrecomillar(texto) {
    return '"' + String(texto).replace(/"/g, "'") + '"';
  }

  var api = {
    crear: function (texto) { return new Yaml(texto); },
    numero: numero,
    siNo: siNo,
    entrecomillar: entrecomillar,
    partirLinea: partirLinea
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NPYaml = api;
})(typeof window !== "undefined" ? window : this);
