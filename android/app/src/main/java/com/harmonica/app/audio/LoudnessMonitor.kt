package com.harmonica.app.audio

import android.content.Context
import android.media.AudioDeviceInfo
import android.media.AudioManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Reads what the browser cannot: the system music-stream volume and the active output device.
 *
 * This is still NOT calibrated dB SPL — true SPL depends on headphone sensitivity and amplifier gain
 * that Android does not expose — but the volume fraction + device type give a far better relative
 * exposure estimate than a web app, and let us be stricter on earbuds than on a speaker.
 */
class LoudnessMonitor(context: Context) {

    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    data class State(
        val volumeFraction: Float,
        val outputType: OutputType,
        /** Relative exposure estimate 0..1; higher = more cautious territory. */
        val exposure: Float
    )

    enum class OutputType { EARBUDS, HEADPHONES, BLUETOOTH, SPEAKER, OTHER }

    private val _state = MutableStateFlow(read())
    val state: StateFlow<State> = _state

    fun refresh() {
        _state.value = read()
    }

    private fun read(): State {
        val max = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC).coerceAtLeast(1)
        val cur = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
        val fraction = cur.toFloat() / max
        val output = currentOutput()
        // Earbuds sit in-canal, so the same volume fraction is treated as more exposure.
        val deviceWeight = when (output) {
            OutputType.EARBUDS -> 1.15f
            OutputType.HEADPHONES -> 1.0f
            OutputType.BLUETOOTH -> 1.0f
            OutputType.SPEAKER -> 0.7f
            OutputType.OTHER -> 0.9f
        }
        val exposure = (fraction * deviceWeight).coerceIn(0f, 1f)
        return State(fraction, output, exposure)
    }

    private fun currentOutput(): OutputType {
        val devices = audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
        for (device in devices) {
            when (device.type) {
                AudioDeviceInfo.TYPE_WIRED_HEADSET,
                AudioDeviceInfo.TYPE_USB_HEADSET -> return OutputType.EARBUDS
                AudioDeviceInfo.TYPE_WIRED_HEADPHONES -> return OutputType.HEADPHONES
                AudioDeviceInfo.TYPE_BLUETOOTH_A2DP,
                AudioDeviceInfo.TYPE_BLE_HEADSET -> return OutputType.BLUETOOTH
                AudioDeviceInfo.TYPE_BUILTIN_SPEAKER -> return OutputType.SPEAKER
            }
        }
        return OutputType.OTHER
    }
}
