using UnityEngine;

/// <summary>
/// Controlador de linterna para el jugador
/// Permite encender/apagar la linterna y gestionar su comportamiento
/// </summary>
public class FlashlightController : MonoBehaviour
{
    [Header("Configuración de Linterna")]
    [SerializeField] private Light flashlight;
    [SerializeField] private KeyCode toggleKey = KeyCode.F;
    [SerializeField] private bool isOn = false;

    [Header("Configuración de Luz")]
    [SerializeField] private float lightIntensity = 2f;
    [SerializeField] private float lightRange = 15f;
    [SerializeField] private float spotAngle = 60f;
    [SerializeField] private Color lightColor = Color.white;

    [Header("Efectos (Opcional)")]
    [SerializeField] private bool enableFlicker = false;
    [SerializeField] private float flickerIntensity = 0.1f;
    [SerializeField] private float flickerSpeed = 10f;

    [Header("Sonidos (Opcional)")]
    [SerializeField] private AudioSource audioSource;
    [SerializeField] private AudioClip toggleOnSound;
    [SerializeField] private AudioClip toggleOffSound;

    private float baseIntensity;
    private float flickerTimer;

    void Start()
    {
        InitializeFlashlight();
        baseIntensity = lightIntensity;

        // Estado inicial
        if (flashlight != null)
        {
            flashlight.enabled = isOn;
        }
    }

    void Update()
    {
        HandleToggle();

        if (isOn && enableFlicker)
        {
            ApplyFlicker();
        }
    }

    private void InitializeFlashlight()
    {
        // Si no se asignó una luz en el inspector, intentar obtenerla del objeto
        if (flashlight == null)
        {
            flashlight = GetComponent<Light>();

            // Si no hay luz, intentar buscarla en los hijos
            if (flashlight == null)
            {
                flashlight = GetComponentInChildren<Light>();
            }

            // Si aún no hay luz, crear una
            if (flashlight == null)
            {
                GameObject lightObject = new GameObject("Flashlight");
                lightObject.transform.SetParent(transform);
                lightObject.transform.localPosition = Vector3.zero;
                lightObject.transform.localRotation = Quaternion.identity;

                flashlight = lightObject.AddComponent<Light>();
            }
        }

        // Configurar la luz
        if (flashlight != null)
        {
            flashlight.type = LightType.Spot;
            flashlight.intensity = lightIntensity;
            flashlight.range = lightRange;
            flashlight.spotAngle = spotAngle;
            flashlight.color = lightColor;
            flashlight.shadows = LightShadows.Soft; // Sombras suaves para mejor apariencia
        }

        // Configurar AudioSource si no existe
        if (audioSource == null)
        {
            audioSource = GetComponent<AudioSource>();
            if (audioSource == null && (toggleOnSound != null || toggleOffSound != null))
            {
                audioSource = gameObject.AddComponent<AudioSource>();
                audioSource.playOnAwake = false;
                audioSource.spatialBlend = 0f; // Sonido 2D
            }
        }
    }

    private void HandleToggle()
    {
        if (Input.GetKeyDown(toggleKey))
        {
            ToggleFlashlight();
        }
    }

    public void ToggleFlashlight()
    {
        isOn = !isOn;

        if (flashlight != null)
        {
            flashlight.enabled = isOn;
        }

        PlayToggleSound();
    }

    public void TurnOn()
    {
        if (!isOn)
        {
            isOn = true;
            if (flashlight != null)
            {
                flashlight.enabled = true;
            }
            PlayToggleSound();
        }
    }

    public void TurnOff()
    {
        if (isOn)
        {
            isOn = false;
            if (flashlight != null)
            {
                flashlight.enabled = false;
            }
            PlayToggleSound();
        }
    }

    private void ApplyFlicker()
    {
        if (flashlight == null) return;

        flickerTimer += Time.deltaTime * flickerSpeed;
        float flicker = Mathf.PerlinNoise(flickerTimer, 0f) * flickerIntensity;
        flashlight.intensity = baseIntensity + flicker;
    }

    private void PlayToggleSound()
    {
        if (audioSource == null) return;

        if (isOn && toggleOnSound != null)
        {
            audioSource.PlayOneShot(toggleOnSound);
        }
        else if (!isOn && toggleOffSound != null)
        {
            audioSource.PlayOneShot(toggleOffSound);
        }
    }

    // Métodos públicos para acceder al estado
    public bool IsFlashlightOn()
    {
        return isOn;
    }

    public void SetIntensity(float intensity)
    {
        lightIntensity = intensity;
        baseIntensity = intensity;
        if (flashlight != null && isOn)
        {
            flashlight.intensity = intensity;
        }
    }

    public void SetRange(float range)
    {
        lightRange = range;
        if (flashlight != null)
        {
            flashlight.range = range;
        }
    }
}
