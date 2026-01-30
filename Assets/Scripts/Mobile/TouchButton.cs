using UnityEngine;
using UnityEngine.UI;
using UnityEngine.Events;
using UnityEngine.EventSystems;

/// <summary>
/// Botón táctil para acciones en móvil (saltar, correr, linterna, etc.)
/// </summary>
public class TouchButton : MonoBehaviour, IPointerDownHandler, IPointerUpHandler
{
    [Header("Configuración")]
    [SerializeField] private ButtonType buttonType = ButtonType.Press;
    [SerializeField] private bool vibrationOnPress = false;

    [Header("Visual Feedback")]
    [SerializeField] private Image buttonImage;
    [SerializeField] private Color normalColor = Color.white;
    [SerializeField] private Color pressedColor = Color.gray;
    [SerializeField] private Color toggleOnColor = Color.green;
    [SerializeField] private float pressScale = 0.9f;

    [Header("Eventos")]
    public UnityEvent OnButtonDown;
    public UnityEvent OnButtonUp;
    public UnityEvent<bool> OnButtonToggle; // Para botones toggle

    // Estado
    private bool isPressed = false;
    private bool isToggled = false;
    private Vector3 originalScale;
    private RectTransform rectTransform;

    public enum ButtonType
    {
        Press,      // Se activa mientras mantienes presionado
        Toggle,     // Se activa/desactiva con cada toque
        Tap         // Se activa una vez al tocar
    }

    public bool IsPressed => isPressed;
    public bool IsToggled => isToggled;

    void Start()
    {
        rectTransform = GetComponent<RectTransform>();
        originalScale = rectTransform.localScale;

        if (buttonImage == null)
        {
            buttonImage = GetComponent<Image>();
        }

        UpdateVisuals();
    }

    public void OnPointerDown(PointerEventData eventData)
    {
        switch (buttonType)
        {
            case ButtonType.Press:
                isPressed = true;
                OnButtonDown?.Invoke();
                break;

            case ButtonType.Toggle:
                isToggled = !isToggled;
                OnButtonToggle?.Invoke(isToggled);
                OnButtonDown?.Invoke();
                break;

            case ButtonType.Tap:
                OnButtonDown?.Invoke();
                break;
        }

        // Feedback visual
        if (rectTransform != null)
        {
            rectTransform.localScale = originalScale * pressScale;
        }

        // Vibración
        if (vibrationOnPress)
        {
            Vibrate();
        }

        UpdateVisuals();
    }

    public void OnPointerUp(PointerEventData eventData)
    {
        switch (buttonType)
        {
            case ButtonType.Press:
                isPressed = false;
                OnButtonUp?.Invoke();
                break;

            case ButtonType.Toggle:
                OnButtonUp?.Invoke();
                break;

            case ButtonType.Tap:
                OnButtonUp?.Invoke();
                break;
        }

        // Restaurar escala
        if (rectTransform != null)
        {
            rectTransform.localScale = originalScale;
        }

        UpdateVisuals();
    }

    private void UpdateVisuals()
    {
        if (buttonImage == null) return;

        Color targetColor = normalColor;

        switch (buttonType)
        {
            case ButtonType.Press:
                targetColor = isPressed ? pressedColor : normalColor;
                break;

            case ButtonType.Toggle:
                targetColor = isToggled ? toggleOnColor : normalColor;
                break;

            case ButtonType.Tap:
                targetColor = normalColor;
                break;
        }

        buttonImage.color = targetColor;
    }

    private void Vibrate()
    {
        #if UNITY_ANDROID || UNITY_IOS
        Handheld.Vibrate();
        #endif
    }

    // Métodos públicos para controlar el botón programáticamente
    public void SetPressed(bool pressed)
    {
        isPressed = pressed;
        UpdateVisuals();
    }

    public void SetToggled(bool toggled)
    {
        isToggled = toggled;
        UpdateVisuals();
    }

    public void ResetButton()
    {
        isPressed = false;
        isToggled = false;
        UpdateVisuals();
    }

    public void SetButtonType(ButtonType type)
    {
        buttonType = type;
        UpdateVisuals();
    }
}
