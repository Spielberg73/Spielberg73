# Juego de Linterna en Primera Persona - Unity

## Descripción
Proyecto de Unity que implementa un juego en primera persona donde el protagonista usa una linterna para iluminarse en entornos oscuros.

## Características
- ✅ Movimiento en primera persona (WASD + Mouse)
- ✅ Sistema de linterna con encendido/apagado
- ✅ Control de cámara con mouse
- ✅ Física básica con gravedad y salto
- ✅ Efectos de parpadeo opcionales para la linterna
- ✅ Soporte para sonidos de linterna

## Requisitos
- Unity 2020.3 LTS o superior (recomendado Unity 2021 o 2022)
- Sistema operativo: Windows, macOS o Linux

## Configuración del Proyecto

### 1. Importar el Proyecto en Unity

1. Abre Unity Hub
2. Haz clic en "Add" o "Agregar"
3. Selecciona la carpeta raíz de este proyecto
4. Selecciona la versión de Unity que deseas usar
5. Haz clic en el proyecto para abrirlo

### 2. Configuración de la Escena

#### Crear el Jugador (Player)

1. En la jerarquía, crea un objeto vacío: `GameObject > Create Empty`
2. Nómbralo "Player"
3. Añade un `CharacterController`:
   - Selecciona el objeto Player
   - En el Inspector: `Add Component > Character Controller`
   - Ajusta el Height a 2 y el Radius a 0.5

4. Añade el script `FirstPersonController`:
   - Con el objeto Player seleccionado
   - `Add Component > FirstPersonController`

5. Crea la cámara del jugador:
   - Click derecho en Player: `Create Empty`
   - Nómbralo "Camera"
   - Posiciónalo en (0, 0.6, 0) para altura de los ojos
   - Si no tienes una cámara, añade: `Add Component > Camera`
   - Asigna esta cámara en el campo "Camera Transform" del FirstPersonController

#### Configurar la Linterna

1. Con el objeto "Camera" seleccionado:
   - Click derecho: `Create Empty`
   - Nómbralo "Flashlight"
   - Posiciónalo ligeramente adelante: (0, -0.2, 0.5)

2. Añade el script de linterna:
   - Con Flashlight seleccionado
   - `Add Component > FlashlightController`
   - El script creará automáticamente un componente Light si no existe

3. Opcional - Personalizar la luz:
   - Ajusta "Light Intensity" (intensidad: 2-5 recomendado)
   - Ajusta "Light Range" (rango: 10-20 recomendado)
   - Ajusta "Spot Angle" (ángulo: 40-80 recomendado)
   - Cambia "Light Color" si deseas un color específico

#### Crear el Entorno

1. Crea un plano para el suelo:
   - `GameObject > 3D Object > Plane`
   - Escálalo a (10, 1, 10) o más grande

2. Añade algunos objetos para probar:
   - `GameObject > 3D Object > Cube` (crea varios)
   - Distribúyelos por la escena

3. **IMPORTANTE**: Configura la iluminación ambiental oscura:
   - `Window > Rendering > Lighting`
   - En la pestaña "Environment":
     - Desactiva "Skybox" o usa uno oscuro
     - Ajusta "Environment Lighting > Source" a "Color"
     - Cambia "Ambient Color" a negro o muy oscuro
   - Elimina la luz direccional por defecto si existe

4. Opcional - Añade un Skybox oscuro:
   - `Assets > Create > Material`
   - Nómbralo "DarkSkybox"
   - Cambia Shader a `Skybox/Procedural`
   - Ajusta los colores a tonos oscuros
   - En `Window > Rendering > Lighting > Environment`
   - Arrastra el material DarkSkybox al campo Skybox Material

### 3. Controles del Juego

- **W/A/S/D**: Movimiento
- **Mouse**: Mirar alrededor
- **F**: Encender/apagar linterna
- **Espacio**: Saltar
- **Shift Izquierdo**: Correr
- **ESC**: Liberar/bloquear cursor

### 4. Configuración Avanzada (Opcional)

#### Efectos de Parpadeo de Linterna
En el componente `FlashlightController`:
- Marca "Enable Flicker"
- Ajusta "Flicker Intensity" (0.05 - 0.2)
- Ajusta "Flicker Speed" (5 - 15)

#### Sonidos de Linterna
1. Importa clips de audio (formato .wav, .mp3, o .ogg)
2. En el componente `FlashlightController`:
   - Asigna "Toggle On Sound"
   - Asigna "Toggle Off Sound"

## Estructura del Proyecto

```
Spielberg73/
├── Assets/
│   ├── Scripts/
│   │   ├── FirstPersonController.cs    # Control del jugador
│   │   └── FlashlightController.cs     # Control de la linterna
│   ├── Scenes/                         # Guarda tus escenas aquí
│   ├── Materials/                      # Materiales del juego
│   └── Prefabs/                        # Prefabs reutilizables
├── ProjectSettings/                    # Configuración de Unity
└── Packages/                           # Paquetes de Unity
```

## Scripts Principales

### FirstPersonController.cs
Controla el movimiento del jugador en primera persona:
- Movimiento WASD con velocidad ajustable
- Control de cámara con mouse
- Sistema de gravedad
- Salto
- Opción de correr

### FlashlightController.cs
Gestiona el sistema de linterna:
- Encendido/apagado con tecla F
- Configuración personalizable de luz
- Efectos de parpadeo opcionales
- Sistema de sonidos opcionales
- Métodos públicos para control programático

## Próximas Características Sugeridas

- 🔋 Sistema de batería para la linterna
- 👻 Enemigos u obstáculos que reaccionen a la luz
- 🎯 Sistema de objetivos o puzzles
- 🔊 Efectos de sonido ambiente
- 🎨 Mejoras visuales y post-procesado
- 🗺️ Sistema de niveles
- 💾 Sistema de guardado

## Solución de Problemas

### El jugador se cae a través del suelo
- Asegúrate de que el plano tenga un Collider
- Verifica que el CharacterController esté configurado correctamente

### La linterna no se ve
- Verifica que la iluminación ambiente esté oscura
- Comprueba que el componente Light esté habilitado
- Ajusta la intensidad y el rango de la luz

### El mouse no funciona
- Asegúrate de hacer clic en la ventana del juego
- Presiona ESC para bloquear el cursor si está liberado
- Verifica que la cámara esté asignada en el FirstPersonController

### El movimiento no funciona
- Verifica que haya un CharacterController en el objeto Player
- Comprueba que el script FirstPersonController esté adjunto
- Asegúrate de que no haya errores en la consola

## Créditos
Proyecto creado con Unity Engine
Scripts desarrollados en C#

## Licencia
Este proyecto es de código abierto y está disponible para uso educativo y personal.
