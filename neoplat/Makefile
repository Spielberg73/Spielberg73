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
test-navegador: ejemplo
	$(PYTHON) tests/navegador.py $(EJEMPLO)/preview.html capturas

# Arranca lo compilado en emuladores de verdad y deja capturas. Necesita los
# cores de libretro; si no estan, cada prueba se salta sola:
#   Mega Drive:  apt-get install libretro-genesisplusgx
#   Amiga:       puae_libretro.so del buildbot de libretro, en /usr/local/lib/libretro
#   Jaguar:      virtualjaguar_libretro.so, del mismo buildbot
#   Atari ST:    hatari_libretro.so, del mismo buildbot, mas una imagen de TOS
#                (EmuTOS vale) en /usr/local/share/neoplat/tos.img
# La Neo Geo va con el banco de pruebas del propio kit (pip3 install amitools).
test-emulador: test-emulador-md test-emulador-amiga test-emulador-neogeo \
               test-emulador-jaguar test-emulador-st

test-emulador-md:
	./ngplat compilar $(EJEMPLO) --sistema megadrive --make
	$(PYTHON) tests/emulador_md.py \
		$(EJEMPLO)/build/megadrive/rom/juego.bin capturas

test-emulador-amiga:
	./ngplat compilar $(EJEMPLO) --sistema amiga --make
	$(PYTHON) tests/emulador_amiga.py \
		$(EJEMPLO)/build/amiga/disco/BosqueMagico.adf capturas

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

ejemplo:
	./ngplat comprobar $(EJEMPLO)
	./ngplat probar $(EJEMPLO) --no-abrir
	./ngplat compilar $(EJEMPLO)

# Compila el ejemplo para las cinco maquinas (necesita un compilador de 68000
# para construir de verdad el cartucho, los disquetes y la ROM).
ejemplo-todos:
	./ngplat compilar $(EJEMPLO) --sistema neogeo
	./ngplat compilar $(EJEMPLO) --sistema megadrive --make
	./ngplat compilar $(EJEMPLO) --sistema amiga --make
	./ngplat compilar $(EJEMPLO) --sistema jaguar --make
	./ngplat compilar $(EJEMPLO) --sistema atarist --make

limpiar:
	rm -rf $(EJEMPLO)/build $(EJEMPLO)/preview.html capturas
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

.PHONY: test test-rapido test-navegador test-emulador test-emulador-md \
	test-emulador-amiga test-emulador-neogeo test-emulador-jaguar \
	test-emulador-st ejemplo ejemplo-todos limpiar
