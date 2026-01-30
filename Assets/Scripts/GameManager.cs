using UnityEngine;

/// <summary>
/// Gestor principal del juego
/// Maneja el estado del juego y configuraciones globales
/// </summary>
public class GameManager : MonoBehaviour
{
    public static GameManager Instance { get; private set; }

    [Header("Configuración del Juego")]
    [SerializeField] private bool pauseOnStart = false;
    [SerializeField] private bool showCursorOnPause = true;

    private bool isPaused = false;

    void Awake()
    {
        // Implementar patrón Singleton
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }

        Instance = this;
        DontDestroyOnLoad(gameObject);
    }

    void Start()
    {
        if (pauseOnStart)
        {
            PauseGame();
        }
    }

    void Update()
    {
        // Pausar/Reanudar con tecla P o ESC (opcional)
        if (Input.GetKeyDown(KeyCode.P))
        {
            TogglePause();
        }
    }

    public void PauseGame()
    {
        isPaused = true;
        Time.timeScale = 0f;

        if (showCursorOnPause)
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }

        Debug.Log("Juego pausado");
    }

    public void ResumeGame()
    {
        isPaused = false;
        Time.timeScale = 1f;

        Cursor.lockState = CursorLockMode.Locked;
        Cursor.visible = false;

        Debug.Log("Juego reanudado");
    }

    public void TogglePause()
    {
        if (isPaused)
        {
            ResumeGame();
        }
        else
        {
            PauseGame();
        }
    }

    public bool IsPaused()
    {
        return isPaused;
    }

    public void QuitGame()
    {
        Debug.Log("Saliendo del juego...");
        #if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
        #else
            Application.Quit();
        #endif
    }
}
