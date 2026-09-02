# Tareas del kit NeoPlat.
#
#   make test      todas las pruebas (herramientas, motor, paridad C/JS)
#   make ejemplo   compila el ejemplo y genera su preview
#   make limpiar   borra lo generado

PYTHON ?= python3
NODE   ?= node
EJEMPLO := examples/bosque-magico

test:
	cd tests && $(PYTHON) -m unittest discover -p 'test_*.py' -v

test-rapido:
	cd tests && $(PYTHON) -m unittest discover -p 'test_*.py'

# Prueba el preview en un navegador de verdad (necesita Playwright).
# La segunda vuelta genera un proyecto con 'jugadores: 2' y comprueba que cada
# teclado mueve al suyo; la tercera levanta el servidor de verdad y comprueba
# el bucle de guardar y recuperar contra la carpeta del proyecto.
test-navegador: ejemplo
	$(PYTHON) tests/navegador.py $(EJEMPLO)/preview.html capturas
	$(PYTHON) tests/navegador.py --dos capturas
	$(PYTHON) tests/navegador.py --guardado capturas

# Arranca lo compilado en emuladores de verdad y deja capturas. Necesita los
# cores de libretro; si no estan, cada prueba se salta sola:
#   Mega Drive:  apt-get install libretro-genesisplusgx
#   Amiga:       puae_libretro.so del buildbot de libretro, en /usr/local/lib/libretro
#   Jaguar:      virtualjaguar_libretro.so, del mismo buildbot
#   Atari ST:    hatari_libretro.so, del mismo buildbot, mas una imagen de TOS
#                (EmuTOS vale) en /usr/local/share/neoplat/tos.img
# La Neo Geo va con el banco de pruebas del propio kit (pip3 install amitools).
test-emulador: test-emulador-md test-emulador-amiga test-emulador-a1200 \
               test-emulador-neogeo test-emulador-jaguar test-emulador-st

test-emulador-md:
	./ngplat compilar $(EJEMPLO) --sistema megadrive --make
	$(PYTHON) tests/emulador_md.py \
		$(EJEMPLO)/build/megadrive/rom/juego.bin capturas

test-emulador-amiga:
	./ngplat compilar $(EJEMPLO) --sistema amiga --make
	$(PYTHON) tests/emulador_amiga.py \
		$(EJEMPLO)/build/amiga/disco/BosqueMagico.adf capturas

# El mismo disquete, con AGA: ocho bitplanes y 256 colores. Se emula un A1200
# porque en un A500 los ocho bitplanes no existen y no se veria nada.
test-emulador-a1200:
	./ngplat compilar $(EJEMPLO) --sistema amiga1200 --make
	$(PYTHON) tests/emulador_amiga.py \
		$(EJEMPLO)/build/amiga1200/disco/BosqueMagico.adf capturas --modelo=A1200

# La Neo Geo no necesita core de libretro: el banco de pruebas del kit trae el
# 68000 (machine68k, de amitools) y el chip de video escrito en Python.
test-emulador-neogeo:
	./ngplat compilar $(EJEMPLO) --sistema neogeo
	$(PYTHON) tests/emulador_neogeo.py $(EJEMPLO)/build/neogeo capturas

test-emulador-jaguar:
	./ngplat compilar $(EJEMPLO) --sistema jaguar --make
	$(PYTHON) tests/emulador_jaguar.py \
		$(EJEMPLO)/build/jaguar/rom/BosqueMagico.j64 capturas

test-emulador-st:
	./ngplat compilar $(EJEMPLO) --sistema atarist --make
	$(PYTHON) tests/emulador_st.py \
		$(EJEMPLO)/build/atarist/disco/bosquema.st capturas

# El X68000 necesita ademas las ROMs de Sharp y un disquete de Human68k, que no
# vienen aqui: se apuntan con NEOPLAT_X68000_ROMS y NEOPLAT_HUMAN68K. Sin ellos
# la prueba se salta sola.
test-emulador-x68000:
	./ngplat compilar $(EJEMPLO) --sistema x68000 --make
	$(PYTHON) tests/emulador_x68000.py \
		$(EJEMPLO)/build/x68000/disco/BOSQUEMA.X capturas

ejemplo:
	./ngplat comprobar $(EJEMPLO)
	./ngplat probar $(EJEMPLO) --no-abrir
	./ngplat compilar $(EJEMPLO)

# Compila el ejemplo para las siete maquinas (necesita un compilador de 68000
# para construir de verdad el cartucho, los disquetes y la ROM).
ejemplo-todos:
	./ngplat compilar $(EJEMPLO) --sistema neogeo
	./ngplat compilar $(EJEMPLO) --sistema megadrive --make
	./ngplat compilar $(EJEMPLO) --sistema amiga --make
	./ngplat compilar $(EJEMPLO) --sistema amiga1200 --make
	./ngplat compilar $(EJEMPLO) --sistema jaguar --make
	./ngplat compilar $(EJEMPLO) --sistema atarist --make
	./ngplat compilar $(EJEMPLO) --sistema x68000 --make

# Los paquetes para repartir: los ZIP de docs y del kit en dist/.
# `paquetes-exe` ademas construye el ngplat.exe de Windows; en Windows sale
# directo, y desde Linux hace falta Wine con un Python de Windows dentro:
#   make paquetes-exe PYTHON_WINDOWS="wine /ruta/a/python.exe"
paquetes:
	$(PYTHON) empaquetar.py

paquetes-exe:
	$(PYTHON) empaquetar.py --exe $(if $(PYTHON_WINDOWS),--python "$(PYTHON_WINDOWS)",)

limpiar:
	rm -rf dist $(EJEMPLO)/build $(EJEMPLO)/preview.html capturas
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

.PHONY: test test-rapido test-navegador test-emulador test-emulador-md \
	test-emulador-amiga test-emulador-a1200 test-emulador-neogeo \
	test-emulador-jaguar \
	test-emulador-st test-emulador-x68000 ejemplo ejemplo-todos paquetes \
	paquetes-exe limpiar
