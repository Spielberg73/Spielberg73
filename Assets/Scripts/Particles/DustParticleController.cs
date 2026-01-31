using UnityEngine;

/// <summary>
/// Controla el sistema de partículas de polvo que aparece en el cono de luz de la linterna.
/// Las partículas solo son visibles cuando la linterna está encendida y crean un efecto atmosférico realista.
///
/// Características:
/// - Partículas que flotan lentamente en el aire
/// - Solo visibles en el cono de luz
/// - Densidad ajustable según el ambiente
/// - Tamaño y velocidad variables para mayor realismo
/// - Iluminación dinámica basada en la luz de la linterna
/// </summary>
public class DustParticleController : MonoBehaviour
{
    [Header("Referencias")]
    [Tooltip("Sistema de partículas principal de polvo")]
    [SerializeField] private ParticleSystem dustParticleSystem;

    [Tooltip("Luz de la linterna (opcional, para sincronización)")]
    [SerializeField] private Light flashlight;

    [Header("Configuración de Emisión")]
    [Tooltip("Número de partículas emitidas por segundo cuando la linterna está encendida")]
    [SerializeField] private float emissionRateWhenActive = 100f;

    [Tooltip("Multiplicador de densidad de polvo (1 = normal, 2 = muy polvoriento)")]
    [SerializeField] private float dustDensityMultiplier = 1f;

    [Tooltip("Activar automáticamente cuando la linterna se enciende")]
    [SerializeField] private bool autoActivateWithFlashlight = true;

    [Header("Configuración de Partículas")]
    [Tooltip("Tamaño mínimo de las partículas de polvo")]
    [SerializeField] private float minParticleSize = 0.01f;

    [Tooltip("Tamaño máximo de las partículas de polvo")]
    [SerializeField] private float maxParticleSize = 0.05f;

    [Tooltip("Velocidad de movimiento del polvo")]
    [SerializeField] private float dustSpeed = 0.2f;

    [Tooltip("Tiempo de vida de las partículas")]
    [SerializeField] private float particleLifetime = 5f;

    [Header("Forma del Emisor")]
    [Tooltip("Ángulo del cono de emisión (debe coincidir con el de la linterna)")]
    [SerializeField] private float coneAngle = 45f;

    [Tooltip("Radio de la base del cono")]
    [SerializeField] private float coneRadius = 5f;

    [Tooltip("Longitud del cono de luz")]
    [SerializeField] private float coneLength = 10f;

    [Header("Efectos Visuales")]
    [Tooltip("Color del polvo")]
    [SerializeField] private Color dustColor = new Color(1f, 1f, 1f, 0.3f);

    [Tooltip("Usar iluminación de la escena")]
    [SerializeField] private bool affectedByLight = true;

    [Header("Optimización")]
    [Tooltip("Distancia máxima de la cámara para renderizar partículas")]
    [SerializeField] private float maxRenderDistance = 50f;

    [Tooltip("Reducir emisión cuando está lejos de la cámara")]
    [SerializeField] private bool useDistanceCulling = true;

    // Estado interno
    private ParticleSystem.EmissionModule emissionModule;
    private ParticleSystem.MainModule mainModule;
    private ParticleSystem.ShapeModule shapeModule;
    private ParticleSystem.ColorOverLifetimeModule colorModule;
    private Transform cameraTransform;
    private bool isFlashlightOn = false;
    private float currentEmissionRate = 0f;

    void Start()
    {
        InitializeParticleSystem();
        cameraTransform = Camera.main?.transform;
    }

    void Update()
    {
        UpdateEmission();
        UpdateDistanceCulling();
    }

    /// <summary>
    /// Inicializa el sistema de partículas con la configuración establecida
    /// </summary>
    private void InitializeParticleSystem()
    {
        if (dustParticleSystem == null)
        {
            Debug.LogError($"DustParticleController en {gameObject.name}: No se asignó el ParticleSystem!");
            return;
        }

        // Obtener módulos del sistema de partículas
        emissionModule = dustParticleSystem.emission;
        mainModule = dustParticleSystem.main;
        shapeModule = dustParticleSystem.shape;
        colorModule = dustParticleSystem.colorOverLifetime;

        // Configurar módulo principal
        mainModule.startLifetime = particleLifetime;
        mainModule.startSpeed = new ParticleSystem.MinMaxCurve(dustSpeed * 0.5f, dustSpeed);
        mainModule.startSize = new ParticleSystem.MinMaxCurve(minParticleSize, maxParticleSize);
        mainModule.startColor = dustColor;
        mainModule.simulationSpace = ParticleSystemSimulationSpace.World;
        mainModule.maxParticles = 1000;

        // Configurar emisión
        emissionModule.enabled = true;
        emissionModule.rateOverTime = 0f; // Empezamos con 0, se actualiza en Update

        // Configurar forma del emisor (cono)
        shapeModule.enabled = true;
        shapeModule.shapeType = ParticleSystemShapeType.Cone;
        shapeModule.angle = coneAngle;
        shapeModule.radius = coneRadius;
        shapeModule.length = coneLength;
        shapeModule.randomDirectionAmount = 0.3f; // Movimiento algo aleatorio

        // Configurar color sobre tiempo de vida (fade out)
        colorModule.enabled = true;
        Gradient gradient = new Gradient();
        gradient.SetKeys(
            new GradientColorKey[] {
                new GradientColorKey(Color.white, 0.0f),
                new GradientColorKey(Color.white, 1.0f)
            },
            new GradientAlphaKey[] {
                new GradientAlphaKey(0.0f, 0.0f),      // Invisible al inicio
                new GradientAlphaKey(dustColor.a, 0.2f), // Fade in rápido
                new GradientAlphaKey(dustColor.a, 0.8f), // Mantiene opacidad
                new GradientAlphaKey(0.0f, 1.0f)       // Fade out al final
            }
        );
        colorModule.color = gradient;

        // Si no hay linterna asignada, buscarla
        if (flashlight == null && autoActivateWithFlashlight)
        {
            flashlight = GetComponentInChildren<Light>();
        }
    }

    /// <summary>
    /// Actualiza la emisión de partículas según el estado de la linterna
    /// </summary>
    private void UpdateEmission()
    {
        if (dustParticleSystem == null) return;

        // Determinar si la linterna está encendida
        bool shouldEmit = false;

        if (autoActivateWithFlashlight && flashlight != null)
        {
            shouldEmit = flashlight.enabled && flashlight.intensity > 0.1f;
        }
        else
        {
            shouldEmit = isFlashlightOn;
        }

        // Calcular emisión objetivo
        float targetEmissionRate = shouldEmit ? emissionRateWhenActive * dustDensityMultiplier : 0f;

        // Transición suave de emisión
        currentEmissionRate = Mathf.Lerp(currentEmissionRate, targetEmissionRate, Time.deltaTime * 5f);
        emissionModule.rateOverTime = currentEmissionRate;

        // Activar/desactivar el sistema según sea necesario
        if (shouldEmit && !dustParticleSystem.isPlaying)
        {
            dustParticleSystem.Play();
        }
        else if (!shouldEmit && currentEmissionRate < 0.1f && dustParticleSystem.isPlaying)
        {
            // Dejamos que termine de emitir antes de detenerlo completamente
            if (dustParticleSystem.particleCount == 0)
            {
                dustParticleSystem.Stop();
            }
        }
    }

    /// <summary>
    /// Reduce la emisión cuando el jugador está lejos para optimizar rendimiento
    /// </summary>
    private void UpdateDistanceCulling()
    {
        if (!useDistanceCulling || cameraTransform == null || dustParticleSystem == null) return;

        float distance = Vector3.Distance(transform.position, cameraTransform.position);

        if (distance > maxRenderDistance)
        {
            // Demasiado lejos, desactivar completamente
            if (dustParticleSystem.isPlaying)
            {
                dustParticleSystem.Stop(true, ParticleSystemStopBehavior.StopEmitting);
            }
        }
        else if (distance > maxRenderDistance * 0.7f)
        {
            // Cerca del límite, reducir emisión gradualmente
            float distanceFactor = 1f - ((distance - maxRenderDistance * 0.7f) / (maxRenderDistance * 0.3f));
            emissionModule.rateOverTimeMultiplier = distanceFactor;
        }
        else
        {
            // Dentro del rango óptimo, emisión completa
            emissionModule.rateOverTimeMultiplier = 1f;
        }
    }

    /// <summary>
    /// Activa la emisión de polvo manualmente
    /// </summary>
    public void ActivateDust()
    {
        isFlashlightOn = true;
    }

    /// <summary>
    /// Desactiva la emisión de polvo manualmente
    /// </summary>
    public void DeactivateDust()
    {
        isFlashlightOn = false;
    }

    /// <summary>
    /// Establece la densidad del polvo en tiempo real
    /// </summary>
    /// <param name="density">Multiplicador de densidad (1 = normal, 2 = muy denso)</param>
    public void SetDustDensity(float density)
    {
        dustDensityMultiplier = Mathf.Max(0f, density);
    }

    /// <summary>
    /// Ajusta el ángulo del cono para coincidir con la linterna
    /// </summary>
    /// <param name="angle">Ángulo en grados</param>
    public void SetConeAngle(float angle)
    {
        coneAngle = Mathf.Clamp(angle, 0f, 90f);
        if (shapeModule.enabled)
        {
            shapeModule.angle = coneAngle;
        }
    }

    /// <summary>
    /// Ajusta el alcance del cono de polvo
    /// </summary>
    /// <param name="length">Longitud del cono</param>
    public void SetConeLength(float length)
    {
        coneLength = Mathf.Max(0f, length);
        if (shapeModule.enabled)
        {
            shapeModule.length = coneLength;
        }
    }

    /// <summary>
    /// Obtiene el número actual de partículas activas
    /// </summary>
    public int GetActiveParticleCount()
    {
        return dustParticleSystem != null ? dustParticleSystem.particleCount : 0;
    }

    #if UNITY_EDITOR
    /// <summary>
    /// Visualiza el cono de emisión en el editor
    /// </summary>
    private void OnDrawGizmosSelected()
    {
        Gizmos.color = new Color(1f, 1f, 0f, 0.3f);

        // Dibujar líneas del cono
        Vector3 forward = transform.forward * coneLength;
        float radiusAtEnd = Mathf.Tan(coneAngle * Mathf.Deg2Rad) * coneLength;

        Vector3 endCenter = transform.position + forward;

        // Dibujar círculo en la base del cono
        DrawWireCircle(endCenter, transform.up, radiusAtEnd, 20);

        // Dibujar líneas desde el origen hasta el borde del cono
        for (int i = 0; i < 8; i++)
        {
            float angle = (i / 8f) * Mathf.PI * 2f;
            Vector3 point = endCenter +
                (transform.right * Mathf.Cos(angle) + transform.up * Mathf.Sin(angle)) * radiusAtEnd;
            Gizmos.DrawLine(transform.position, point);
        }
    }

    private void DrawWireCircle(Vector3 center, Vector3 normal, float radius, int segments)
    {
        Vector3 right = Vector3.Cross(normal, Vector3.up).normalized;
        if (right == Vector3.zero)
            right = Vector3.Cross(normal, Vector3.forward).normalized;
        Vector3 up = Vector3.Cross(right, normal).normalized;

        Vector3 prevPoint = center + right * radius;
        for (int i = 1; i <= segments; i++)
        {
            float angle = (i / (float)segments) * Mathf.PI * 2f;
            Vector3 point = center + (right * Mathf.Cos(angle) + up * Mathf.Sin(angle)) * radius;
            Gizmos.DrawLine(prevPoint, point);
            prevPoint = point;
        }
    }
    #endif
}
