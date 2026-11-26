"""Map button events to actions, by state. Pure, so it is tested exhaustively.

Buttons: "talk" (button 1, the stronger hand) and "no" (button 2, optional).
Gestures: "short" and "long" (held about 1.5 s).

With two buttons each one keeps a single meaning everywhere:
  talk short = speak / stop speaking / stop speech      no short = cancel, no
  talk long  = yes when asked, otherwise repeat         no long  = help

With one button the old mapping holds: talk long = cancel, or help when idle.
"""

from __future__ import annotations

from .lang import L

TALK, NO = "talk", "no"
SHORT, LONG = "short", "long"

IDLE, RECORDING, CONFIRMING, THINKING = "idle", "recording", "confirming", "thinking"

# actions
A_TALK, A_STOP, A_CANCEL, A_YES, A_NO, A_REPEAT, A_HELP, A_REASSURE, A_NONE = (
    "talk", "stop", "cancel", "yes", "no", "repeat", "help", "reassure", "none",
)

Event = tuple[str, str]  # (button, gesture)


def interpret(event: Event, state: str, two_buttons: bool) -> str:
    button, gesture = event
    if button == NO:
        if not two_buttons:
            return A_NONE
        if state == IDLE:
            return A_HELP if gesture == LONG else A_NONE
        if state == CONFIRMING:
            return A_NO
        return A_CANCEL  # recording or thinking
    # button == TALK
    if state == IDLE:
        if gesture == SHORT:
            return A_TALK
        return A_REPEAT if two_buttons else A_HELP
    if state == RECORDING:
        if gesture == SHORT or two_buttons:
            return A_STOP
        return A_CANCEL
    if state == CONFIRMING:
        if gesture == SHORT:
            return A_TALK
        return A_YES if two_buttons else A_CANCEL
    if state == THINKING:
        if gesture == SHORT or two_buttons:
            return A_REASSURE
        return A_CANCEL
    return A_NONE


def help_text(two_buttons: bool) -> str:
    if two_buttons:
        return L(
            "Button one: press to talk and press again to finish. Hold it to say yes when I ask, "
            "or to hear the last reply again. "
            "Button two: press to cancel or say no. Hold it to hear this help. "
            "To move a page, say 'scroll down', 'a little more', 'again' or 'go up'. "
            "Say 'new conversation' to start something else while a task goes on, and 'conversation one' to go back. "
            "Say 'update' to look for improvements, or 'undo' to go back to the previous version.",
            "Botón uno: pulsa para hablar y otra vez para terminar. Mantenlo pulsado para decir sí "
            "cuando te pregunte, o para repetir la última respuesta. "
            "Botón dos: pulsa para cancelar o decir no. Mantenlo pulsado para oír esta ayuda. "
            "Para mover una página di 'baja', 'baja un poco', 'otra vez' o 've hacia arriba'. "
            "Di 'nueva conversación' para empezar otra cosa mientras una tarea sigue, y 'conversación uno' para volver. "
            "Di 'actualiza' para buscar mejoras, o 'deshacer' para volver a la versión anterior.")
    return L(
        "Press once to talk and once more to finish. Hold to cancel. "
        "Say 'repeat' to hear the last reply, 'scroll down' or 'go up' to move a page, 'new conversation' to start "
        "something else while a task goes on, 'update' to look for improvements, or 'undo' to go back to the "
        "previous version.",
        "Pulsa una vez para hablar y otra vez para terminar. Mantén pulsado para cancelar. "
        "Di 'repite' para oír la última respuesta, 'baja' o 've hacia arriba' para mover una página, "
        "'nueva conversación' para empezar otra cosa mientras una tarea sigue, 'actualiza' para buscar mejoras, "
        "o 'deshacer' para volver a la versión anterior.")
