# 👣 Sistema Profesional de Pasos - Guía Completa

## Descripción
Sistema avanzado de footsteps con detección de superficies, variación de sonidos, efectos de partículas y sincronización con movimiento. Nivel AAA comparable a Half-Life, FEAR, o Call of Duty.

---

## ✨ Características Principales

### 🎵 Sistema de Audio Avanzado
- ✅ **13 tipos de superficie** diferentes (concreto, madera, metal, césped, etc.)
- ✅ **Variación aleatoria** de sonidos (múltiples clips por superficie)
- ✅ **Volumen y pitch dinámicos** con variación
- ✅ **Audio 3D opcional** con atenuación por distancia
- ✅ **Reverb configurable** por superficie

### 🔍 Detección Inteligente de Superficie
- ✅ **3 métodos de detección**:
  1. **SurfaceIdentifier** (componente específico) - Prioritario
  2. **Physics Material** (automático) - Secundario
  3. **Tag del objeto** (fallback) - Terciario
- ✅ **Raycast optimizado** hacia abajo
- ✅ **Detección en tiempo real** cada frame

### 🎬 Sincronización con Movimiento
- ✅ **Velocidad adaptativa**: Diferentes intervalos para caminar/correr
- ✅ **Solo en suelo**: Opción para no reproducir en el aire
- ✅ **Umbral de velocidad**: No reproduce si está quieto
- ✅ **Sincronización con Head Bob** (opcional)

### 💫 Efectos Visuales
- ✅ **Partículas por superficie** (polvo, salpicaduras, etc.)
- ✅ **Pool de objetos** para optimización
- ✅ **Spawn chance configurable** (no siempre aparecen)
- ✅ **Custom effects** por superficie específica

### ⚙️ Sistema Modular
- ✅ **ScriptableObjects** para datos
- ✅ **Fácil de extender** nuevas superficies
- ✅ **Sin hardcoding** de valores
- ✅ **Configuración en Inspector**

---

## 🚀 Configuración Rápida (15 minutos)

### Paso 1: Añadir Componentes al Jugador

```
1. Selecciona el objeto Player
2. Add Component > Surface Detector
3. Add Component > Footstep System
4. Add Component > Footstep HeadBob Sync (opcional)
```

### Paso 2: Configurar Surface Detector

```
Inspector > Surface Detector:
- Detection Origin: (dejar vacío para auto-detectar)
- Raycast Distance: 1.5
- Surface Layer Mask: Everything
- Default Surface: Concrete
- Use Physics Material Mapping: ✅
- Use Tag Mapping: ✅
- Show Debug Ray: ❌ (activar para visualizar)
```

### Paso 3: Crear Footstep Data (Datos de Superficie)

```
1. Click derecho en Project > Create > Audio > Footstep Data
2. Renombrar a "Footsteps_Concrete" (o la superficie que sea)
3. Configurar:
   - Surface Type: Concrete
   - Surface Name: "Concreto"
   - Footstep Sounds: (arrastra 3-5 clips de audio)
   - Volume: 0.5
   - Volume Variation: 0.1
   - Pitch: 1.0
   - Pitch Variation: 0.1
   - Walk Step Interval: 0.5
   - Run Step Interval: 0.3
   - Particle Effect: (opcional, un prefab de partículas)
```

### Paso 4: Configurar Footstep System

```
Inspector > Footstep System:

Componentes Requeridos:
- Surface Detector: (auto-asignado)
- Character Controller: (auto-asignado)
- Player Controller: (auto-asignado)

Datos de Superficies:
- Footstep Data List: (arrastra todos los FootstepData creados)
- Default Footstep Data: (arrastra uno como fallback)

Configuración General:
- Enable Footsteps: ✅
- Master Volume: 0.7
- Play Only When Grounded: ✅
- Min Velocity For Footsteps: 0.1

Sincronización:
- Sync With Head Bob: ✅
- Walk Speed Threshold: 4

Efectos de Partículas:
- Enable Particles: ✅
- Particle Spawn Point: (auto-creado)
- Particle Lifetime: 2

Audio Avanzado:
- Use 3D Audio: ❌ (activar para multi jugador)
- Max Audio Distance: 20
```

### Paso 5: Crear Superficies en el Mundo

#### Opción A: Usar SurfaceIdentifier (Recomendado)
```
1. Selecciona un objeto 3D (ej: Plane para suelo)
2. Add Component > Surface Identifier
3. Configurar:
   - Surface Type: (elegir el tipo)
   - Override Physics Material: ✅
   - Volume Multiplier: 1.0
   - Pitch Multiplier: 1.0
```

#### Opción B: Usar Physics Material
```
1. Assets > Create > Physic Material
2. Nombrar "Wood_PhysicMat" (incluir nombre del material)
3. Asignar al Collider del objeto
4. El sistema lo detectará automáticamente por nombre
```

#### Opción C: Usar Tags
```
1. Selecciona objeto
2. Tag: (crear tag "Wood", "Metal", etc.)
3. El sistema lo detectará por tag
```

---

## 🎵 Preparar Audio

### Grabar/Obtener Sonidos

#### Fuentes Recomendadas:
- **Freesound.org** (gratis, licencia Creative Commons)
- **Zapsplat.com** (gratis para proyectos indie)
- **Unity Asset Store** (muchos packs gratis)
- **Grabar propios** con smartphone (añade autenticidad)

#### Recomendaciones por Superficie:
```
Concreto: 4-6 clips (pisadas secas, eco corto)
Madera: 4-6 clips (crujidos, tonos medios)
Metal: 3-5 clips (agudo, resonante)
Césped: 5-7 clips (suave, natural)
Grava: 5-7 clips (crujiente, variado)
Arena: 4-6 clips (suave, amortiguado)
Agua: 4-6 clips (chapoteo, salpicaduras)
```

### Importar en Unity

```
1. Crear carpeta: Assets/Audio/Footsteps/Concrete/
2. Arrastrar archivos WAV o MP3
3. Seleccionar todos los clips
4. Inspector:
   - Force To Mono: ✅ (ahorra memoria)
   - Load Type: Compressed In Memory
   - Compression Format: Vorbis
   - Quality: 70-80%
   - Sample Rate: 22050 Hz (suficiente para footsteps)
```

---

## 🎨 Crear Efectos de Partículas

### Sistema de Partículas Básico

```
1. GameObject > Effects > Particle System
2. Renombrar "FootstepDust"
3. Configurar:

Main Module:
- Duration: 0.5
- Looping: ❌
- Start Lifetime: 0.3-0.5
- Start Speed: 0.5-2
- Start Size: 0.1-0.3
- Start Color: Gris/Marrón según superficie
- Gravity Modifier: 0.5
- Max Particles: 10

Emission:
- Rate over Time: 0
- Bursts: 1 burst, Count: 5-10

Shape:
- Shape: Circle
- Radius: 0.2
- Randomize Direction: 0.3

4. Convertir a Prefab (arrastra a Project)
5. Asignar en FootstepData
```

### Efectos Específicos por Superficie

| Superficie | Color | Partículas | Forma |
|------------|-------|-----------|-------|
| Concreto | Gris claro | Polvo fino | Nube baja |
| Madera | Marrón | Astillas | Disperso |
| Metal | Blanco/Azul | Chispas | Rápido |
| Césped | Verde | Hojas | Suave |
| Grava | Gris oscuro | Piedras | Disperso |
| Arena | Amarillo | Arena | Nube densa |
| Agua | Azul | Gotas | Splash |
| Nieve | Blanco | Nieve | Nube suave |

---

## ⚙️ Configuración Avanzada

### FootstepData - Parámetros Detallados

#### Audio
```csharp
// Volumen
Volume: 0.5              // Volumen base
Volume Variation: 0.1    // ±10% de variación aleatoria

// Pitch
Pitch: 1.0              // Tono base
Pitch Variation: 0.1    // ±10% de variación aleatoria

// Intervalos
Walk Step Interval: 0.5  // Tiempo entre pasos caminando
Run Step Interval: 0.3   // Tiempo entre pasos corriendo

// Reverb (opcional)
Use Reverb: ❌          // Activar eco
Reverb Amount: 0.3      // Cantidad de reverberación
```

**Recomendaciones**:
- **Volumen base**: 0.3-0.7 (footsteps no deben ser demasiado fuertes)
- **Variación**: 0.05-0.15 (suficiente para realismo, no tanto que suene raro)
- **Pitch**: 0.8-1.2 (rango natural de variación)
- **Intervalos caminando**: 0.4-0.6 segundos
- **Intervalos corriendo**: 0.25-0.35 segundos

#### Partículas
```csharp
Particle Effect: Prefab      // Prefab del sistema de partículas
Particle Spawn Chance: 0.8   // 80% probabilidad de aparecer
```

**Uso**:
- **Spawn Chance < 1.0**: Más realista (no siempre hay polvo visible)
- **Spawn Chance = 1.0**: Siempre hay efecto (más espectacular)

### SurfaceDetector - Detección Avanzada

```csharp
// Raycast
Raycast Distance: 1.5        // Distancia hacia abajo
Surface Layer Mask: Everything // Qué capas detectar

// Prioridad de Detección
1. SurfaceIdentifier (si existe en el objeto)
2. Physics Material (por nombre)
3. Tag (fallback)

// Mapeo de Physics Materials
"wood_phys" → Wood
"metal_phys" → Metal
"grass_phys" → Grass
etc. (ver código para lista completa)
```

**Tips**:
- Usa **SurfaceIdentifier** para control preciso
- Usa **Physics Material** para mapeo automático
- Usa **Tags** para objetos simples

### FootstepSystem - Configuración Avanzada

#### Audio 3D
```csharp
Use 3D Audio: ✅
Max Audio Distance: 20       // Máxima distancia audible
Spatial Blend: 1.0          // 100% espacial

// Curva de atenuación (en AudioSource)
Volume Rolloff: Logarithmic
Min Distance: 1
Max Distance: 20
```

**Cuándo usar**:
- **Multiplayer**: ✅ (escuchar pasos de otros jugadores)
- **Single player primera persona**: ❌ (sin necesidad)
- **Tercera persona**: ✅ (escuchar al personaje)

#### Sincronización con Head Bob
```csharp
Sync With Head Bob: ✅
```

**Nota**: El FootstepHeadBobSync es **opcional** pero recomendado para:
- Mayor inmersión
- Sincronización visual-audio perfecta
- Sensación de "peso" en el movimiento

---

## 🎯 Casos de Uso Específicos

### Juego de Terror
```
Master Volume: 0.3-0.5    // Pasos más sutiles
Enable Particles: ❌      // Sin distracciones visuales
Use Reverb: ✅           // Ambiente inquietante
Walk Step Interval: 0.6   // Pasos más lentos y pesados
```

### Juego de Acción
```
Master Volume: 0.6-0.8    // Pasos audibles
Enable Particles: ✅      // Feedback visual
Use Reverb: ❌           // Sin reverb (claridad)
Run Step Interval: 0.25   // Pasos rápidos
```

### Juego Sigilo
```
Master Volume: Variable    // Según velocidad
Enable Particles: ✅      // Alerta visual (enemigos ven polvo)
Walk Step Interval: 0.7   // Caminar muy lento
Run Step Interval: 0.2    // Correr muy audible
```

### Multijugador
```
Use 3D Audio: ✅
Max Audio Distance: 15-25
Volume: 0.5-0.7
Enable Particles: ✅      // Todos ven las partículas
```

---

## 🔧 Crear Nuevas Superficies

### Paso a Paso Completo

#### 1. Crear FootstepData
```
Assets > Create > Audio > Footstep Data
Nombre: "Footsteps_MiSuperficie"
```

#### 2. Configurar Audio
```
Surface Type: (crear nuevo en el enum si no existe)
Surface Name: "Mi Superficie"
Footstep Sounds: (5-7 clips variados)
Volume: 0.5
Walk Step Interval: 0.5
Run Step Interval: 0.3
```

#### 3. Crear Partículas (Opcional)
```
- Crear Particle System
- Configurar según el material
- Convertir a Prefab
- Asignar en FootstepData
```

#### 4. Añadir al FootstepSystem
```
- Seleccionar Player
- Footstep System > Footstep Data List
- Añadir elemento
- Arrastra el nuevo FootstepData
```

#### 5. Identificar Objetos
```
Opción A: Add Component > Surface Identifier
          Surface Type: MiSuperficie

Opción B: Physics Material con nombre "misuperficie"

Opción C: Tag "MiSuperficie"
```

---

## 🐛 Solución de Problemas

### Problema 1: No se escuchan pasos
**Síntomas**: El jugador se mueve pero sin sonido

**Soluciones**:
```
1. Verificar Enable Footsteps: ✅
2. Verificar Master Volume > 0
3. Verificar que FootstepData tenga clips asignados
4. Verificar que Min Velocity For Footsteps sea bajo (0.1)
5. Inspector > FootstepSystem > Show Debug Info: ✅
   (Ver si detecta movimiento)
```

### Problema 2: Superficie no detectada
**Síntomas**: Siempre usa superficie "Default"

**Soluciones**:
```
1. Verificar que el objeto tenga Collider
2. Verificar LayerMask en SurfaceDetector
3. Añadir SurfaceIdentifier al objeto
4. Verificar que Raycast Distance sea suficiente
5. Activar Show Debug Ray para ver el raycast
```

### Problema 3: Pasos demasiado rápidos/lentos
**Síntomas**: Ritmo de pasos no coincide con movimiento

**Soluciones**:
```
1. Ajustar Walk Step Interval (0.4-0.6)
2. Ajustar Run Step Interval (0.25-0.35)
3. Verificar Walk Speed Threshold (debe coincidir con velocidad de sprint)
4. Activar Sync With Head Bob para sincronización perfecta
```

### Problema 4: Todos los pasos suenan igual
**Síntomas**: Falta variación

**Soluciones**:
```
1. Añadir más clips de audio (mínimo 4-5)
2. Aumentar Volume Variation (0.1-0.15)
3. Aumentar Pitch Variation (0.1-0.15)
4. Usar clips grabados diferentes, no copias
```

### Problema 5: Partículas no aparecen
**Síntomas**: No hay efectos visuales

**Soluciones**:
```
1. Verificar Enable Particles: ✅
2. Verificar que FootstepData tenga Particle Effect asignado
3. Verificar Particle Spawn Chance > 0
4. Verificar que el prefab tenga Particle System component
5. Aumentar Particle Lifetime si desaparecen muy rápido
```

### Problema 6: Pasos en el aire
**Síntomas**: Se escuchan pasos al saltar

**Soluciones**:
```
1. Verificar Play Only When Grounded: ✅
2. Verificar que CharacterController esté asignado
3. Verificar que el suelo tenga collider
```

---

## 📊 Optimización

### Performance Tips

#### Audio
```
- Use Compressed In Memory para clips
- Sample Rate: 22050 Hz (suficiente)
- Force To Mono: ✅
- Compression Format: Vorbis (70-80%)
- Máximo 10 clips por superficie
```

#### Partículas
```
- Max Particles: 10-20 (no más)
- Particle Lifetime: 1-2 segundos
- Use Pool de objetos (ya implementado)
- Spawn Chance < 1.0 para menos partículas
```

#### Detección
```
- Raycast Distance: Justo necesario (1.5)
- Update frecuency: Cada frame está OK
- Use Layer Mask para excluir objetos innecesarios
```

### Métricas Recomendadas
```
- Clips de audio: 40-70 total (todas las superficies)
- Tamaño de cada clip: 20-100 KB comprimido
- Partículas activas simultáneas: < 50
- Overhead CPU: < 1% (sistema muy optimizado)
```

---

## 🎓 Tips Profesionales

### 1. Variación es Clave
```
NO: 2 clips que suenan muy similares
SÍ: 5-7 clips con variaciones notables

Graba:
- Diferentes intensidades
- Diferentes partes del pie (talón, punta)
- Diferentes ángulos de pisada
```

### 2. Contexto Ambiental
```
Interiores:
- Más reverb
- Volumen más bajo
- Pasos más "cercanos"

Exteriores:
- Sin reverb
- Volumen normal
- Pasos más "abiertos"
```

### 3. Peso del Personaje
```
Personaje pesado:
- Pitch más bajo (0.8-0.9)
- Volumen más alto (0.7-0.8)
- Intervalos más largos (0.6-0.7)

Personaje ligero:
- Pitch más alto (1.1-1.2)
- Volumen más bajo (0.3-0.5)
- Intervalos más cortos (0.4-0.5)
```

### 4. Narrativa Audio
```
Los pasos pueden contar una historia:
- Urgencia (pasos rápidos, irregulares)
- Cansancio (pasos lentos, pesados)
- Sigilo (pasos muy suaves)
- Confianza (pasos firmes, regulares)
```

### 5. Sincronización Perfecta
```
Para máximo realismo:
1. Activar Sync With Head Bob
2. Ajustar intervalos hasta que coincidan visualmente
3. Test con diferentes velocidades
4. Ajustar Sync Offset si es necesario (-0.05 a 0.05)
```

---

## 📚 Referencia de API

### FootstepSystem

```csharp
// Métodos públicos
void EnableFootsteps(bool enable)
void SetMasterVolume(float volume)
void PlayManualFootstep()
SurfaceType GetCurrentSurface()
bool IsMoving()
bool IsRunning()
```

### SurfaceDetector

```csharp
// Propiedades
SurfaceType CurrentSurface { get; }
SurfaceIdentifier CurrentSurfaceIdentifier { get; }
RaycastHit LastHit { get; }

// Métodos
void ForceDetection()
void SetSurfaceType(SurfaceType type)
void SetRaycastDistance(float distance)
```

### FootstepData

```csharp
// Métodos
AudioClip GetRandomFootstepSound()
float GetRandomVolume()
float GetRandomPitch()
bool ShouldSpawnParticles()
```

---

## 🎬 Ejemplo de Configuración Completa

### Juego Completo con 5 Superficies

```
1. Crear 5 FootstepData:
   - Footsteps_Concrete
   - Footsteps_Wood
   - Footsteps_Metal
   - Footsteps_Grass
   - Footsteps_Water

2. Cada uno con:
   - 5 clips de audio variados
   - Volumen 0.5, variación 0.1
   - Pitch 1.0, variación 0.1
   - Intervalos: Walk 0.5, Run 0.3
   - Partículas según material

3. Crear objetos en escena:
   - Suelo principal (Plane) → SurfaceIdentifier: Concrete
   - Plataforma de madera → SurfaceIdentifier: Wood
   - Puente metálico → SurfaceIdentifier: Metal
   - Zona de césped → SurfaceIdentifier: Grass
   - Charco de agua → SurfaceIdentifier: Water

4. Player configurado:
   - Surface Detector ✅
   - Footstep System ✅
   - 5 FootstepData asignados
   - Master Volume: 0.7
   - Enable Footsteps: ✅
   - Enable Particles: ✅

5. Test:
   - Caminar por cada superficie
   - Verificar sonidos diferentes
   - Verificar partículas
   - Ajustar intervalos si es necesario
```

---

## 🚀 Próximas Mejoras Sugeridas

### Opcionales (puedes añadir):
- 🎵 Sonidos de aterrizaje (al caer de altura)
- 💦 Efectos de agua profunda (chapoteo constante)
- ❄️ Efectos de nieve profunda (pasos amortiguados)
- 🌿 Sonidos de vegetación al pasar (arbustos)
- 🔊 Sistema de audio occlusion
- 📊 Visualizador de formas de onda
- 🎚️ Mixer de audio con ducking
- 🎭 Diferentes sets según personaje

---

**Versión**: 1.0
**Última actualización**: 2026-01-30
**Compatibilidad**: Unity 6.0 / 2022.3 LTS
**Nivel**: Profesional AAA

---

¡Sistema de pasos completo y listo para producción! 👣🎵
