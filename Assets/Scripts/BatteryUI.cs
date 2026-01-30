using UnityEngine;
using UnityEngine.UI;
using TMPro;

/// <summary>
/// UI Manager para mostrar el nivel de batería y otros elementos de interfaz
/// </summary>
public class BatteryUI : MonoBehaviour
{
    [Header("Referencias")]
    [SerializeField] private BatterySystem batterySystem;

    [Header("UI - Barra de Batería")]
    [SerializeField] private Slider batterySlider;
    [SerializeField] private Image batteryFillImage;
    [SerializeField] private TextMeshProUGUI batteryText;

    [Header("UI - Icono de Batería")]
    [SerializeField] private Image batteryIcon;
    [SerializeField] private Sprite batteryFullIcon;
    [SerializeField] private Sprite batteryMediumIcon;
    [SerializeField] private Sprite batteryLowIcon;
    [SerializeField] private Sprite batteryEmptyIcon;

    [Header("Colores de Batería")]
    [SerializeField] private Color fullColor = Color.green;
    [SerializeField] private Color mediumColor = Color.yellow;
    [SerializeField] private Color lowColor = new Color(1f, 0.5f, 0f); // Naranja
    [SerializeField] private Color criticalColor = Color.red;

    [Header("Animaciones")]
    [SerializeField] private bool enablePulseAnimation = true;
    [SerializeField] private float pulseSpeed = 2f;
    [SerializeField] private float pulseIntensity = 0.3f;

    [Header("Configuración")]
    [SerializeField] private bool hideWhenFull = false;
    [SerializeField] private bool hideWhenDisabled = true;
    [SerializeField] private float updateInterval = 0.1f;

    private float lastUpdateTime;
    private CanvasGroup canvasGroup;
    private bool isLowBattery = false;
    private bool isCriticalBattery = false;

    void Start()
    {
        // Buscar BatterySystem si no está asignado
        if (batterySystem == null)
        {
            batterySystem = FindObjectOfType<BatterySystem>();
        }

        // Configurar CanvasGroup para fades
        canvasGroup = GetComponent<CanvasGroup>();
        if (canvasGroup == null)
        {
            canvasGroup = gameObject.AddComponent<CanvasGroup>();
        }

        // Suscribirse a eventos si existe el sistema de batería
        if (batterySystem != null)
        {
            batterySystem.OnBatteryChanged.AddListener(UpdateBatteryDisplay);
            batterySystem.OnBatteryLow.AddListener(OnBatteryLow);
            batterySystem.OnBatteryCritical.AddListener(OnBatteryCritical);
            batterySystem.OnBatteryEmpty.AddListener(OnBatteryEmpty);
        }

        // Actualización inicial
        UpdateBatteryDisplay(100f);
    }

    void Update()
    {
        // Actualizar periódicamente
        if (Time.time - lastUpdateTime >= updateInterval)
        {
            if (batterySystem != null)
            {
                UpdateBatteryDisplay(batterySystem.GetBatteryPercentage());
            }
            lastUpdateTime = Time.time;
        }

        // Animación de pulso en batería baja
        if (enablePulseAnimation && (isLowBattery || isCriticalBattery))
        {
            AnimatePulse();
        }
    }

    private void UpdateBatteryDisplay(float percentage)
    {
        // Comprobar si el sistema de batería está habilitado
        if (batterySystem != null && !batterySystem.IsBatteryEnabled())
        {
            if (hideWhenDisabled)
            {
                canvasGroup.alpha = 0f;
                return;
            }
        }

        // Ocultar si está llena y la opción está activada
        if (hideWhenFull && percentage >= 99f)
        {
            canvasGroup.alpha = 0f;
            return;
        }

        canvasGroup.alpha = 1f;

        // Actualizar slider
        if (batterySlider != null)
        {
            batterySlider.value = percentage / 100f;
        }

        // Actualizar texto
        if (batteryText != null)
        {
            batteryText.text = $"{percentage:F0}%";
        }

        // Actualizar color según nivel
        Color currentColor = GetColorForPercentage(percentage);
        if (batteryFillImage != null)
        {
            batteryFillImage.color = currentColor;
        }

        // Actualizar icono
        if (batteryIcon != null)
        {
            batteryIcon.sprite = GetIconForPercentage(percentage);
            batteryIcon.color = currentColor;
        }

        // Determinar estado
        isLowBattery = percentage <= 20f && percentage > 5f;
        isCriticalBattery = percentage <= 5f;
    }

    private Color GetColorForPercentage(float percentage)
    {
        if (percentage <= 5f)
            return criticalColor;
        else if (percentage <= 20f)
            return lowColor;
        else if (percentage <= 50f)
            return mediumColor;
        else
            return fullColor;
    }

    private Sprite GetIconForPercentage(float percentage)
    {
        if (percentage <= 5f)
            return batteryEmptyIcon;
        else if (percentage <= 20f)
            return batteryLowIcon;
        else if (percentage <= 50f)
            return batteryMediumIcon;
        else
            return batteryFullIcon;
    }

    private void AnimatePulse()
    {
        float pulse = Mathf.Sin(Time.time * pulseSpeed) * pulseIntensity + 1f;

        if (batteryIcon != null)
        {
            batteryIcon.transform.localScale = Vector3.one * pulse;
        }
    }

    private void OnBatteryLow()
    {
        isLowBattery = true;
        Debug.Log("UI: Batería baja");
    }

    private void OnBatteryCritical()
    {
        isCriticalBattery = true;
        Debug.Log("UI: Batería crítica");
    }

    private void OnBatteryEmpty()
    {
        Debug.Log("UI: Batería vacía");
    }

    void OnDestroy()
    {
        // Desuscribirse de eventos
        if (batterySystem != null)
        {
            batterySystem.OnBatteryChanged.RemoveListener(UpdateBatteryDisplay);
            batterySystem.OnBatteryLow.RemoveListener(OnBatteryLow);
            batterySystem.OnBatteryCritical.RemoveListener(OnBatteryCritical);
            batterySystem.OnBatteryEmpty.RemoveListener(OnBatteryEmpty);
        }
    }

    // Métodos públicos para configuración
    public void SetBatterySystem(BatterySystem system)
    {
        batterySystem = system;
    }

    public void Show()
    {
        canvasGroup.alpha = 1f;
    }

    public void Hide()
    {
        canvasGroup.alpha = 0f;
    }
}
