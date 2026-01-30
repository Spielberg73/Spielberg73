using UnityEngine;

/// <summary>
/// Sincroniza el sistema de pasos con el Head Bob para mayor realismo
/// Los pasos se reproducen cuando el "pie" toca el suelo en la animación de cabeza
/// </summary>
[RequireComponent(typeof(FootstepSystem))]
public class FootstepHeadBobSync : MonoBehaviour
{
    [Header("Referencias")]
    [SerializeField] private FirstPersonController playerController;
    [SerializeField] private FootstepSystem footstepSystem;

    [Header("Configuración de Sincronización")]
    [SerializeField] private bool enableSync = true;
    [SerializeField] private float headBobThreshold = 0.02f; // Cuando el head bob cruza este punto, reproduce paso
    [SerializeField] private bool useZeroCrossing = true; // Detectar cuando la cabeza pasa por el centro

    [Header("Ajuste Fino")]
    [SerializeField] private float syncOffset = 0f; // Offset en segundos para ajustar timing
    [SerializeField] private int stepsPerCycle = 2; // Cuántos pasos por ciclo de head bob

    [Header("Debug")]
    [SerializeField] private bool showDebugInfo = false;

    // Estado interno
    private float lastHeadBobValue = 0f;
    private bool lastWasPositive = false;
    private int stepCounter = 0;

    void Start()
    {
        if (playerController == null)
        {
            playerController = GetComponent<FirstPersonController>();
        }

        if (footstepSystem == null)
        {
            footstepSystem = GetComponent<FootstepSystem>();
        }

        if (playerController == null || footstepSystem == null)
        {
            Debug.LogWarning("FootstepHeadBobSync: Faltan componentes requeridos");
            enabled = false;
        }
    }

    void Update()
    {
        if (!enableSync) return;
        if (!playerController.IsGrounded()) return;
        if (playerController.GetSpeed() < 0.1f) return;

        DetectHeadBobStep();
    }

    private void DetectHeadBobStep()
    {
        // Obtener valor actual del head bob
        // Nota: Esto requiere exponer el headBobTimer en FirstPersonController
        // Por ahora usamos una aproximación basada en tiempo

        float currentTime = Time.time;
        float bobSpeed = playerController.IsSprinting() ? 18f : 14f; // Valores del FirstPersonController
        float headBobValue = Mathf.Sin(currentTime * bobSpeed);

        // Método 1: Zero Crossing (cuando la onda sinusoidal cruza 0)
        if (useZeroCrossing)
        {
            bool currentIsPositive = headBobValue > 0;

            // Detectar cruce de cero
            if (currentIsPositive != lastWasPositive)
            {
                // Alternar entre pie izquierdo y derecho
                if (stepCounter % stepsPerCycle == 0)
                {
                    TriggerFootstep("Zero crossing");
                }
                stepCounter++;
            }

            lastWasPositive = currentIsPositive;
        }
        // Método 2: Threshold (cuando cruza un umbral específico)
        else
        {
            if (Mathf.Abs(headBobValue) < headBobThreshold && Mathf.Abs(lastHeadBobValue) >= headBobThreshold)
            {
                TriggerFootstep("Threshold");
            }
        }

        lastHeadBobValue = headBobValue;
    }

    private void TriggerFootstep(string method)
    {
        if (footstepSystem != null)
        {
            // Pequeño delay opcional para ajustar timing
            if (syncOffset > 0)
            {
                Invoke(nameof(PlayDelayedFootstep), syncOffset);
            }
            else
            {
                footstepSystem.PlayManualFootstep();
            }

            if (showDebugInfo)
            {
                Debug.Log($"Footstep triggered via {method}");
            }
        }
    }

    private void PlayDelayedFootstep()
    {
        if (footstepSystem != null)
        {
            footstepSystem.PlayManualFootstep();
        }
    }

    // Métodos públicos
    public void SetSyncEnabled(bool enabled)
    {
        enableSync = enabled;
    }

    public void SetSyncOffset(float offset)
    {
        syncOffset = offset;
    }

    public void ResetStepCounter()
    {
        stepCounter = 0;
    }

    // Debug GUI
    void OnGUI()
    {
        if (!showDebugInfo) return;

        GUIStyle style = new GUIStyle();
        style.fontSize = 12;
        style.normal.textColor = Color.cyan;

        int y = 350;
        GUI.Label(new Rect(10, y, 300, 20), $"HeadBob Sync: {enableSync}", style);
        y += 20;
        GUI.Label(new Rect(10, y, 300, 20), $"Step Counter: {stepCounter}", style);
        y += 20;
        GUI.Label(new Rect(10, y, 300, 20), $"Last HeadBob: {lastHeadBobValue:F3}", style);
    }
}
