using UnityEngine;

/// <summary>
/// Interfaz para objetos con los que el jugador puede interactuar
/// </summary>
public interface IInteractable
{
    /// <summary>
    /// Nombre del objeto interactuable
    /// </summary>
    string GetInteractionPrompt();

    /// <summary>
    /// Método llamado cuando el jugador interactúa con el objeto
    /// </summary>
    /// <param name="player">El GameObject del jugador que interactúa</param>
    void Interact(GameObject player);

    /// <summary>
    /// Comprueba si el objeto puede ser interactuado en este momento
    /// </summary>
    bool CanInteract();

    /// <summary>
    /// Transform del objeto (para calcular distancias, etc.)
    /// </summary>
    Transform GetTransform();
}
