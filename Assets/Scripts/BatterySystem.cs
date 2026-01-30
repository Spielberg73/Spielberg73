using UnityEngine;
using UnityEngine.Events;

/// <summary>
/// Sistema de batería para la linterna
/// Gestiona el consumo, recarga y eventos relacionados con la batería
/// </summary>
public class BatterySystem : MonoBehaviour
{
    [Header("Configuración de Batería")]
    [SerializeField] private bool batteryEnabled = true;
    [SerializeField] private float maxBattery = 100f;
    [SerializeField] private float currentBattery = 100f;
    [SerializeField] private float drainRate = 5f; // Porcentaje por segundo

    [Header("Configuración de Recarga")]
    [SerializeField] private float batteryPickupAmount = 25f; // Cantidad que da cada batería
    [SerializeField] private bool allowOvercharge = false;

    [Header("Configuración de Advertencias")]
    [SerializeField] private float lowBatteryThreshold = 20f;
    [SerializeField] private float criticalBatteryThreshold = 5f;

    [Header("Eventos")]
    public UnityEvent OnBatteryEmpty;
    public UnityEvent OnBatteryLow;
    public UnityEvent OnBatteryCritical;
    public UnityEvent<float> OnBatteryChanged; // Pasa el porcentaje actual

    private bool isLowBatteryWarningShown = false;
    private bool isCriticalBatteryWarningShown = false;
    private bool isDraining = false;

    void Start()
    {
        if (!batteryEnabled)
        {
            currentBattery = maxBattery;
        }

        UpdateBatteryUI();
    }

    void Update()
    {
        if (!batteryEnabled) return;

        if (isDraining && currentBattery > 0)
        {
            ConsumeBattery(drainRate * Time.deltaTime);
        }

        CheckBatteryWarnings();
    }

    /// <summary>
    /// Inicia el drenaje de batería
    /// </summary>
    public void StartDraining()
    {
        if (batteryEnabled)
        {
            isDraining = true;
        }
    }

    /// <summary>
    /// Detiene el drenaje de batería
    /// </summary>
    public void StopDraining()
    {
        isDraining = false;
    }

    /// <summary>
    /// Consume batería
    /// </summary>
    private void ConsumeBattery(float amount)
    {
        currentBattery -= amount;
        currentBattery = Mathf.Clamp(currentBattery, 0f, maxBattery);

        UpdateBatteryUI();

        if (currentBattery <= 0)
        {
            OnBatteryDepleted();
        }
    }

    /// <summary>
    /// Añade batería (cuando se recoge una batería)
    /// </summary>
    public void AddBattery(float amount)
    {
        if (!batteryEnabled) return;

        float previousBattery = currentBattery;
        currentBattery += amount;

        if (!allowOvercharge)
        {
            currentBattery = Mathf.Clamp(currentBattery, 0f, maxBattery);
        }

        UpdateBatteryUI();

        // Reset warnings if battery is recharged
        if (previousBattery <= lowBatteryThreshold && currentBattery > lowBatteryThreshold)
        {
            isLowBatteryWarningShown = false;
            isCriticalBatteryWarningShown = false;
        }

        Debug.Log($"Batería recargada: +{amount}%. Total: {currentBattery}%");
    }

    /// <summary>
    /// Recoge una batería (cantidad por defecto)
    /// </summary>
    public void PickupBattery()
    {
        AddBattery(batteryPickupAmount);
    }

    /// <summary>
    /// Comprueba si hay suficiente batería
    /// </summary>
    public bool HasBattery()
    {
        if (!batteryEnabled) return true;
        return currentBattery > 0;
    }

    /// <summary>
    /// Obtiene el porcentaje actual de batería
    /// </summary>
    public float GetBatteryPercentage()
    {
        return (currentBattery / maxBattery) * 100f;
    }

    /// <summary>
    /// Obtiene el valor actual de batería
    /// </summary>
    public float GetCurrentBattery()
    {
        return currentBattery;
    }

    /// <summary>
    /// Comprueba si la batería está activada
    /// </summary>
    public bool IsBatteryEnabled()
    {
        return batteryEnabled;
    }

    /// <summary>
    /// Activa o desactiva el sistema de batería
    /// </summary>
    public void SetBatteryEnabled(bool enabled)
    {
        batteryEnabled = enabled;
        if (!enabled)
        {
            currentBattery = maxBattery;
            isDraining = false;
        }
        UpdateBatteryUI();
    }

    /// <summary>
    /// Recarga la batería al máximo
    /// </summary>
    public void RechargeToFull()
    {
        currentBattery = maxBattery;
        isLowBatteryWarningShown = false;
        isCriticalBatteryWarningShown = false;
        UpdateBatteryUI();
    }

    private void OnBatteryDepleted()
    {
        isDraining = false;
        OnBatteryEmpty?.Invoke();
        Debug.LogWarning("¡Batería agotada!");
    }

    private void CheckBatteryWarnings()
    {
        if (!batteryEnabled) return;

        // Advertencia crítica
        if (currentBattery <= criticalBatteryThreshold && !isCriticalBatteryWarningShown)
        {
            isCriticalBatteryWarningShown = true;
            OnBatteryCritical?.Invoke();
            Debug.LogWarning($"¡BATERÍA CRÍTICA! {currentBattery:F1}%");
        }
        // Advertencia baja
        else if (currentBattery <= lowBatteryThreshold && !isLowBatteryWarningShown)
        {
            isLowBatteryWarningShown = true;
            OnBatteryLow?.Invoke();
            Debug.LogWarning($"Batería baja: {currentBattery:F1}%");
        }
    }

    private void UpdateBatteryUI()
    {
        OnBatteryChanged?.Invoke(GetBatteryPercentage());
    }

    // Métodos para ajustar configuración en runtime
    public void SetDrainRate(float rate)
    {
        drainRate = rate;
    }

    public void SetBatteryPickupAmount(float amount)
    {
        batteryPickupAmount = amount;
    }

    public void SetMaxBattery(float max)
    {
        maxBattery = max;
        currentBattery = Mathf.Clamp(currentBattery, 0f, maxBattery);
        UpdateBatteryUI();
    }

    // Debug info
    void OnGUI()
    {
        if (!batteryEnabled) return;

        // Solo mostrar en modo desarrollo
        #if UNITY_EDITOR
        GUIStyle style = new GUIStyle();
        style.fontSize = 14;
        style.normal.textColor = GetBatteryColor();

        string status = isDraining ? "DRENANDO" : "INACTIVO";
        GUI.Label(new Rect(10, 10, 300, 20),
            $"Batería: {currentBattery:F1}% / {maxBattery}% [{status}]", style);
        #endif
    }

    private Color GetBatteryColor()
    {
        if (currentBattery <= criticalBatteryThreshold) return Color.red;
        if (currentBattery <= lowBatteryThreshold) return Color.yellow;
        return Color.green;
    }
}
