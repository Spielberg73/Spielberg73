using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>
/// Controlador de linterna para el jugador con Input System
/// Integrado con el sistema de batería y efectos avanzados
/// </summary>
public class FlashlightController : MonoBehaviour
{
    [Header("Referencias")]
    [SerializeField] private Light flashlight;
    [SerializeField] private BatterySystem batterySystem;

    [Header("Configuración de Luz")]
    [SerializeField] private bool isOn = false;
    [SerializeField] private float lightIntensity = 3f;
    [SerializeField] private float lightRange = 15f;
    [SerializeField] private float spotAngle = 60f;
    [SerializeField] private Color lightColor = new Color(1f, 0.95f, 0.84f); // Luz cálida

    [Header("Efectos de Batería Baja")]
    [SerializeField] private bool enableLowBatteryEffects = true;
    [SerializeField] private float lowBatteryIntensityMultiplier = 0.5f;
    [SerializeField] private float criticalBatteryFlickerSpeed = 5f;

    [Header("Efectos de Parpadeo")]
    [SerializeField] private bool enableFlicker = false;
    [SerializeField] private float flickerIntensity = 0.1f;
    [SerializeField] private float flickerSpeed = 10f;

    [Header("Transiciones Suaves")]
    [SerializeField] private float fadeSpeed = 8f;
    [SerializeField] private bool smoothTransitions = true;

    [Header("Sonidos")]
    [SerializeField] private AudioSource audioSource;
    [SerializeField] private AudioClip toggleOnSound;
    [SerializeField] private AudioClip toggleOffSound;
    [SerializeField] private AudioClip lowBatterySound;
    [SerializeField] private AudioClip outOfBatterySound;

    private PlayerInputActions inputActions;
    private float baseIntensity;
    private float targetIntensity;
    private float currentIntensity;
    private float flickerTimer;
    private bool lowBatteryWarningPlayed = false;
    private bool isBatteryDepleted = false;

    void Awake()
    {
        inputActions = new PlayerInputActions();
    }

    void OnEnable()
    {
        inputActions.Player.Enable();
        inputActions.Player.Flashlight.performed += OnFlashlightToggle;
    }

    void OnDisable()
    {
        inputActions.Player.Flashlight.performed -= OnFlashlightToggle;
        inputActions.Player.Disable();
    }

    void Start()
    {
        InitializeFlashlight();
        InitializeBatterySystem();

        baseIntensity = lightIntensity;
        targetIntensity = isOn ? lightIntensity : 0f;
        currentIntensity = targetIntensity;

        // Estado inicial
        if (flashlight != null)
        {
            flashlight.enabled = isOn;
            flashlight.intensity = currentIntensity;
        }
    }

    void Update()
    {
        if (flashlight == null) return;

        UpdateFlashlightEffects();
        UpdateBatteryEffects();
        ApplySmoothTransitions();
    }

    private void InitializeFlashlight()
    {
        // Si no se asignó una luz, intentar encontrarla o crearla
        if (flashlight == null)
        {
            flashlight = GetComponent<Light>();

            if (flashlight == null)
            {
                flashlight = GetComponentInChildren<Light>();
            }

            if (flashlight == null)
            {
                GameObject lightObject = new GameObject("FlashlightLight");
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
            flashlight.shadows = LightShadows.Soft;
        }

        // Configurar AudioSource
        if (audioSource == null)
        {
            audioSource = GetComponent<AudioSource>();
            if (audioSource == null)
            {
                audioSource = gameObject.AddComponent<AudioSource>();
                audioSource.playOnAwake = false;
                audioSource.spatialBlend = 0f;
            }
        }
    }

    private void InitializeBatterySystem()
    {
        // Buscar BatterySystem en el jugador
        if (batterySystem == null)
        {
            batterySystem = GetComponentInParent<BatterySystem>();
            if (batterySystem == null)
            {
                batterySystem = FindObjectOfType<BatterySystem>();
            }
        }

        // Suscribirse a eventos de batería
        if (batterySystem != null)
        {
            batterySystem.OnBatteryEmpty.AddListener(OnBatteryDepleted);
            batterySystem.OnBatteryLow.AddListener(OnBatteryLow);
            batterySystem.OnBatteryCritical.AddListener(OnBatteryCritical);
        }
    }

    private void OnFlashlightToggle(InputAction.CallbackContext context)
    {
        ToggleFlashlight();
    }

    public void ToggleFlashlight()
    {
        // Comprobar si hay batería antes de encender
        if (!isOn && batterySystem != null && batterySystem.IsBatteryEnabled())
        {
            if (!batterySystem.HasBattery())
            {
                PlaySound(outOfBatterySound);
                Debug.Log("¡Sin batería!");
                return;
            }
        }

        isOn = !isOn;

        if (isOn)
        {
            TurnOn();
        }
        else
        {
            TurnOff();
        }
    }

    public void TurnOn()
    {
        if (batterySystem != null && batterySystem.IsBatteryEnabled() && !batterySystem.HasBattery())
        {
            PlaySound(outOfBatterySound);
            return;
        }

        isOn = true;
        targetIntensity = baseIntensity;

        if (flashlight != null)
        {
            flashlight.enabled = true;
        }

        // Iniciar drenaje de batería
        if (batterySystem != null)
        {
            batterySystem.StartDraining();
        }

        PlaySound(toggleOnSound);
        isBatteryDepleted = false;
        lowBatteryWarningPlayed = false;
    }

    public void TurnOff()
    {
        isOn = false;
        targetIntensity = 0f;

        // Detener drenaje de batería
        if (batterySystem != null)
        {
            batterySystem.StopDraining();
        }

        PlaySound(toggleOffSound);
    }

    private void UpdateFlashlightEffects()
    {
        if (!isOn) return;

        // Parpadeo normal
        if (enableFlicker)
        {
            flickerTimer += Time.deltaTime * flickerSpeed;
            float flicker = Mathf.PerlinNoise(flickerTimer, 0f) * flickerIntensity;
            targetIntensity = baseIntensity + flicker;
        }
    }

    private void UpdateBatteryEffects()
    {
        if (!enableLowBatteryEffects || batterySystem == null || !batterySystem.IsBatteryEnabled())
            return;

        float batteryPercentage = batterySystem.GetBatteryPercentage();

        // Efectos de batería baja
        if (batteryPercentage <= 5f) // Crítico
        {
            // Parpadeo rápido
            float criticalFlicker = Mathf.Sin(Time.time * criticalBatteryFlickerSpeed) * 0.5f + 0.5f;
            targetIntensity = baseIntensity * lowBatteryIntensityMultiplier * criticalFlicker;
        }
        else if (batteryPercentage <= 20f) // Bajo
        {
            // Reducir intensidad
            targetIntensity = Mathf.Lerp(
                baseIntensity * lowBatteryIntensityMultiplier,
                baseIntensity,
                (batteryPercentage - 5f) / 15f
            );
        }
    }

    private void ApplySmoothTransitions()
    {
        if (smoothTransitions)
        {
            currentIntensity = Mathf.Lerp(currentIntensity, targetIntensity, fadeSpeed * Time.deltaTime);
        }
        else
        {
            currentIntensity = targetIntensity;
        }

        if (flashlight != null)
        {
            flashlight.intensity = currentIntensity;

            // Apagar completamente si la intensidad es muy baja
            if (currentIntensity < 0.01f && !isOn)
            {
                flashlight.enabled = false;
            }
        }
    }

    private void OnBatteryDepleted()
    {
        if (isOn)
        {
            TurnOff();
            PlaySound(outOfBatterySound);
            isBatteryDepleted = true;
        }
    }

    private void OnBatteryLow()
    {
        if (!lowBatteryWarningPlayed && isOn)
        {
            PlaySound(lowBatterySound);
            lowBatteryWarningPlayed = true;
        }
    }

    private void OnBatteryCritical()
    {
        if (isOn)
        {
            PlaySound(lowBatterySound);
        }
    }

    private void PlaySound(AudioClip clip)
    {
        if (audioSource != null && clip != null)
        {
            audioSource.PlayOneShot(clip);
        }
    }

    // Métodos públicos
    public bool IsFlashlightOn()
    {
        return isOn;
    }

    public void SetIntensity(float intensity)
    {
        lightIntensity = intensity;
        baseIntensity = intensity;

        if (isOn)
        {
            targetIntensity = intensity;
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

    public void SetColor(Color color)
    {
        lightColor = color;
        if (flashlight != null)
        {
            flashlight.color = color;
        }
    }

    public float GetCurrentIntensity()
    {
        return currentIntensity;
    }

    public BatterySystem GetBatterySystem()
    {
        return batterySystem;
    }

    void OnDestroy()
    {
        // Desuscribirse de eventos
        if (batterySystem != null)
        {
            batterySystem.OnBatteryEmpty.RemoveListener(OnBatteryDepleted);
            batterySystem.OnBatteryLow.RemoveListener(OnBatteryLow);
            batterySystem.OnBatteryCritical.RemoveListener(OnBatteryCritical);
        }
    }
}
