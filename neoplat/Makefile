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

ejemplo:
	./ngplat comprobar $(EJEMPLO)
	./ngplat probar $(EJEMPLO) --no-abrir
	./ngplat compilar $(EJEMPLO)

# Compila el ejemplo para las tres maquinas (necesita un compilador de 68000
# para construir de verdad el cartucho y el ejecutable).
ejemplo-todos:
	./ngplat compilar $(EJEMPLO) --sistema neogeo
	./ngplat compilar $(EJEMPLO) --sistema megadrive --make
	./ngplat compilar $(EJEMPLO) --sistema amiga --make

limpiar:
	rm -rf $(EJEMPLO)/build $(EJEMPLO)/preview.html capturas
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

.PHONY: test test-rapido test-navegador ejemplo ejemplo-todos limpiar
