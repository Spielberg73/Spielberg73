using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// Sistema profesional de pasos con detección de superficie, variación de sonidos y efectos
/// Compatible con FirstPersonController y MovementController
/// </summary>
[RequireComponent(typeof(AudioSource))]
public class FootstepSystem : MonoBehaviour
{
    [Header("Componentes Requeridos")]
    [SerializeField] private SurfaceDetector surfaceDetector;
    [SerializeField] private CharacterController characterController;
    [SerializeField] private FirstPersonController playerController;

    [Header("Datos de Superficies")]
    [Tooltip("Lista de datos de pasos para cada tipo de superficie")]
    [SerializeField] private List<FootstepData> footstepDataList = new List<FootstepData>();
    [SerializeField] private FootstepData defaultFootstepData;

    [Header("Configuración General")]
    [SerializeField] private bool enableFootsteps = true;
    [SerializeField] [Range(0f, 1f)] private float masterVolume = 0.7f;
    [SerializeField] private bool playOnlyWhenGrounded = true;
    [SerializeField] private float minVelocityForFootsteps = 0.1f;

    [Header("Sincronización con Movimiento")]
    [SerializeField] private bool syncWithHeadBob = true;
    [SerializeField] private float walkSpeedThreshold = 4f;

    [Header("Efectos de Partículas")]
    [SerializeField] private bool enableParticles = true;
    [SerializeField] private Transform particleSpawnPoint;
    [SerializeField] private float particleLifetime = 2f;

    [Header("Audio Avanzado")]
    [SerializeField] private bool use3DAudio = false;
    [SerializeField] private float maxAudioDistance = 20f;
    [SerializeField] private AudioReverbFilter reverbFilter;

    [Header("Debug")]
    [SerializeField] private bool showDebugInfo = false;
    [SerializeField] private bool logFootsteps = false;

    // Estado interno
    private AudioSource audioSource;
    private Dictionary<SurfaceType, FootstepData> footstepDataDictionary;
    private float stepTimer;
    private float currentStepInterval;
    private bool isMoving;
    private bool isRunning;
    private SurfaceType lastSurface;
    private int footstepCount = 0;

    // Pool de objetos para partículas
    private Queue<GameObject> particlePool = new Queue<GameObject>();
    private const int PARTICLE_POOL_SIZE = 10;

    void Start()
    {
        SetupComponents();
        BuildFootstepDictionary();
        InitializeParticlePool();
    }

    void Update()
    {
        if (!enableFootsteps) return;

        UpdateMovementState();
        HandleFootsteps();
    }

    private void SetupComponents()
    {
        // AudioSource
        audioSource = GetComponent<AudioSource>();
        if (audioSource == null)
        {
            audioSource = gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;
        audioSource.spatialBlend = use3DAudio ? 1f : 0f;
        audioSource.maxDistance = maxAudioDistance;

        // SurfaceDetector
        if (surfaceDetector == null)
        {
            surfaceDetector = GetComponent<SurfaceDetector>();
            if (surfaceDetector == null)
            {
                surfaceDetector = gameObject.AddComponent<SurfaceDetector>();
            }
        }

        // CharacterController
        if (characterController == null)
        {
            characterController = GetComponent<CharacterController>();
        }

        // PlayerController
        if (playerController == null)
        {
            playerController = GetComponent<FirstPersonController>();
        }

        // Particle spawn point
        if (particleSpawnPoint == null)
        {
            GameObject spawnPoint = new GameObject("ParticleSpawnPoint");
            spawnPoint.transform.SetParent(transform);
            spawnPoint.transform.localPosition = Vector3.zero;
            particleSpawnPoint = spawnPoint.transform;
        }

        // Reverb filter
        if (reverbFilter == null)
        {
            reverbFilter = GetComponent<AudioReverbFilter>();
        }
    }

    private void BuildFootstepDictionary()
    {
        footstepDataDictionary = new Dictionary<SurfaceType, FootstepData>();

        foreach (FootstepData data in footstepDataList)
        {
            if (data != null)
            {
                if (!footstepDataDictionary.ContainsKey(data.SurfaceType))
                {
                    footstepDataDictionary.Add(data.SurfaceType, data);
                }
                else
                {
                    Debug.LogWarning($"Duplicate FootstepData for {data.SurfaceType}. Using first one.");
                }
            }
        }

        Debug.Log($"FootstepSystem: Loaded {footstepDataDictionary.Count} surface types");
    }

    private void InitializeParticlePool()
    {
        if (!enableParticles) return;

        // Pool vacío por ahora, se llenará según necesidad
        particlePool.Clear();
    }

    private void UpdateMovementState()
    {
        // Detectar movimiento
        if (characterController != null)
        {
            Vector3 velocity = characterController.velocity;
            velocity.y = 0; // Ignorar movimiento vertical
            float speed = velocity.magnitude;

            isMoving = speed > minVelocityForFootsteps;
            isRunning = speed > walkSpeedThreshold;
        }
        else if (playerController != null)
        {
            float speed = playerController.GetSpeed();
            isMoving = speed > minVelocityForFootsteps;
            isRunning = playerController.IsSprinting();
        }
        else
        {
            // Fallback: asumir que no se mueve
            isMoving = false;
            isRunning = false;
        }

        // Comprobar si está en el suelo
        if (playOnlyWhenGrounded)
        {
            if (characterController != null)
            {
                isMoving = isMoving && characterController.isGrounded;
            }
            else if (playerController != null)
            {
                isMoving = isMoving && playerController.IsGrounded();
            }
        }
    }

    private void HandleFootsteps()
    {
        if (!isMoving)
        {
            stepTimer = 0;
            return;
        }

        // Obtener datos de la superficie actual
        SurfaceType currentSurface = surfaceDetector.CurrentSurface;
        FootstepData currentData = GetFootstepData(currentSurface);

        if (currentData == null)
        {
            if (logFootsteps)
            {
                Debug.LogWarning($"No footstep data for surface: {currentSurface}");
            }
            return;
        }

        // Determinar intervalo según velocidad
        currentStepInterval = isRunning ? currentData.RunStepInterval : currentData.WalkStepInterval;

        // Acumular tiempo
        stepTimer += Time.deltaTime;

        // Reproducir paso si es momento
        if (stepTimer >= currentStepInterval)
        {
            PlayFootstep(currentSurface, currentData);
            stepTimer = 0;
        }
    }

    private void PlayFootstep(SurfaceType surface, FootstepData data)
    {
        // Obtener clip aleatorio
        AudioClip clip = data.GetRandomFootstepSound();
        if (clip == null) return;

        // Configurar audio
        audioSource.clip = clip;
        audioSource.volume = data.GetRandomVolume() * masterVolume;
        audioSource.pitch = data.GetRandomPitch();

        // Reverb (si está habilitado)
        if (reverbFilter != null && data.UseReverb)
        {
            reverbFilter.enabled = true;
            reverbFilter.reverbLevel = data.ReverbAmount * 1000f - 10000f; // Convertir a rango Unity
        }
        else if (reverbFilter != null)
        {
            reverbFilter.enabled = false;
        }

        // Aplicar modificadores de SurfaceIdentifier si existe
        if (surfaceDetector.CurrentSurfaceIdentifier != null)
        {
            audioSource.volume *= surfaceDetector.CurrentSurfaceIdentifier.GetVolumeMultiplier();
            audioSource.pitch *= surfaceDetector.CurrentSurfaceIdentifier.GetPitchMultiplier();
        }

        // Reproducir
        audioSource.Play();

        // Efectos de partículas
        if (enableParticles && data.ShouldSpawnParticles())
        {
            SpawnParticleEffect(data.ParticleEffect);
        }

        // Log
        if (logFootsteps)
        {
            Debug.Log($"Footstep #{++footstepCount}: {surface} | Vol: {audioSource.volume:F2} | Pitch: {audioSource.pitch:F2}");
        }

        // Callback para cambio de superficie
        if (lastSurface != surface)
        {
            OnSurfaceChanged(lastSurface, surface);
            lastSurface = surface;
        }
    }

    private FootstepData GetFootstepData(SurfaceType surface)
    {
        if (footstepDataDictionary.TryGetValue(surface, out FootstepData data))
        {
            return data;
        }

        // Fallback al default
        return defaultFootstepData;
    }

    private void SpawnParticleEffect(GameObject particlePrefab)
    {
        if (particlePrefab == null) return;

        // Usar custom effect de SurfaceIdentifier si existe
        if (surfaceDetector.CurrentSurfaceIdentifier != null)
        {
            GameObject customEffect = surfaceDetector.CurrentSurfaceIdentifier.GetCustomParticleEffect();
            if (customEffect != null)
            {
                particlePrefab = customEffect;
            }
        }

        // Spawn en posición del jugador (cerca del suelo)
        Vector3 spawnPosition = particleSpawnPoint.position;

        // Ajustar a superficie detectada si hay hit
        if (surfaceDetector.LastHit.collider != null)
        {
            spawnPosition = surfaceDetector.LastHit.point + Vector3.up * 0.01f;
        }

        // Instanciar
        GameObject particle = Instantiate(particlePrefab, spawnPosition, Quaternion.identity);

        // Auto-destruir
        Destroy(particle, particleLifetime);
    }

    private void OnSurfaceChanged(SurfaceType from, SurfaceType to)
    {
        if (showDebugInfo)
        {
            Debug.Log($"Surface changed: {from} → {to}");
        }
    }

    // Métodos públicos para control externo
    public void EnableFootsteps(bool enable)
    {
        enableFootsteps = enable;
    }

    public void SetMasterVolume(float volume)
    {
        masterVolume = Mathf.Clamp01(volume);
    }

    public void PlayManualFootstep()
    {
        if (!enableFootsteps) return;

        SurfaceType currentSurface = surfaceDetector.CurrentSurface;
        FootstepData currentData = GetFootstepData(currentSurface);

        if (currentData != null)
        {
            PlayFootstep(currentSurface, currentData);
        }
    }

    public SurfaceType GetCurrentSurface()
    {
        return surfaceDetector.CurrentSurface;
    }

    public bool IsMoving()
    {
        return isMoving;
    }

    public bool IsRunning()
    {
        return isRunning;
    }

    // Debug GUI
    void OnGUI()
    {
        if (!showDebugInfo) return;

        GUIStyle style = new GUIStyle();
        style.fontSize = 14;
        style.normal.textColor = Color.white;
        style.normal.background = Texture2D.whiteTexture;

        int y = 250;
        GUI.backgroundColor = new Color(0, 0, 0, 0.5f);

        GUI.Label(new Rect(10, y, 300, 20), $"Footstep System", style);
        y += 20;
        GUI.Label(new Rect(10, y, 300, 20), $"Surface: {surfaceDetector.CurrentSurface}", style);
        y += 20;
        GUI.Label(new Rect(10, y, 300, 20), $"Moving: {isMoving} | Running: {isRunning}", style);
        y += 20;
        GUI.Label(new Rect(10, y, 300, 20), $"Step Timer: {stepTimer:F2} / {currentStepInterval:F2}", style);
        y += 20;
        GUI.Label(new Rect(10, y, 300, 20), $"Total Steps: {footstepCount}", style);
    }
}
