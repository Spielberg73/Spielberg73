using UnityEngine;

/// <summary>
/// ScriptableObject que contiene los sonidos y configuración de pasos para una superficie
/// Crear con: Assets > Create > Audio > Footstep Data
/// </summary>
[CreateAssetMenu(fileName = "New Footstep Data", menuName = "Audio/Footstep Data", order = 1)]
public class FootstepData : ScriptableObject
{
    [Header("Identificación")]
    [SerializeField] private SurfaceType surfaceType = SurfaceType.Default;
    [SerializeField] private string surfaceName = "Nueva Superficie";

    [Header("Sonidos de Pasos")]
    [Tooltip("Lista de clips de audio para variar los sonidos de pasos")]
    [SerializeField] private AudioClip[] footstepSounds;

    [Header("Configuración de Audio")]
    [SerializeField] [Range(0f, 1f)] private float volume = 0.5f;
    [SerializeField] [Range(0f, 1f)] private float volumeVariation = 0.1f;
    [SerializeField] [Range(0.5f, 2f)] private float pitch = 1f;
    [SerializeField] [Range(0f, 0.5f)] private float pitchVariation = 0.1f;

    [Header("Timing")]
    [SerializeField] [Range(0.1f, 2f)] private float walkStepInterval = 0.5f;
    [SerializeField] [Range(0.1f, 2f)] private float runStepInterval = 0.3f;

    [Header("Efectos de Partículas")]
    [SerializeField] private GameObject particleEffect;
    [SerializeField] [Range(0f, 1f)] private float particleSpawnChance = 0.8f;

    [Header("Reverb (Opcional)")]
    [SerializeField] private bool useReverb = false;
    [SerializeField] [Range(0f, 1f)] private float reverbAmount = 0.3f;

    // Propiedades públicas
    public SurfaceType SurfaceType => surfaceType;
    public string SurfaceName => surfaceName;
    public AudioClip[] FootstepSounds => footstepSounds;
    public float Volume => volume;
    public float VolumeVariation => volumeVariation;
    public float Pitch => pitch;
    public float PitchVariation => pitchVariation;
    public float WalkStepInterval => walkStepInterval;
    public float RunStepInterval => runStepInterval;
    public GameObject ParticleEffect => particleEffect;
    public float ParticleSpawnChance => particleSpawnChance;
    public bool UseReverb => useReverb;
    public float ReverbAmount => reverbAmount;

    /// <summary>
    /// Obtiene un clip de audio aleatorio de la lista
    /// </summary>
    public AudioClip GetRandomFootstepSound()
    {
        if (footstepSounds == null || footstepSounds.Length == 0)
        {
            Debug.LogWarning($"No hay sonidos de pasos configurados para {surfaceName}");
            return null;
        }

        return footstepSounds[Random.Range(0, footstepSounds.Length)];
    }

    /// <summary>
    /// Obtiene un volumen aleatorio dentro del rango de variación
    /// </summary>
    public float GetRandomVolume()
    {
        return volume + Random.Range(-volumeVariation, volumeVariation);
    }

    /// <summary>
    /// Obtiene un pitch aleatorio dentro del rango de variación
    /// </summary>
    public float GetRandomPitch()
    {
        return pitch + Random.Range(-pitchVariation, pitchVariation);
    }

    /// <summary>
    /// Determina si debe spawnearse un efecto de partículas
    /// </summary>
    public bool ShouldSpawnParticles()
    {
        return particleEffect != null && Random.value <= particleSpawnChance;
    }

    /// <summary>
    /// Valida que los datos sean correctos
    /// </summary>
    void OnValidate()
    {
        if (footstepSounds != null)
        {
            for (int i = 0; i < footstepSounds.Length; i++)
            {
                if (footstepSounds[i] == null)
                {
                    Debug.LogWarning($"Slot {i} de sonidos de pasos está vacío en {name}");
                }
            }
        }

        if (walkStepInterval < runStepInterval)
        {
            Debug.LogWarning($"Walk interval debería ser mayor que run interval en {name}");
        }
    }
}
