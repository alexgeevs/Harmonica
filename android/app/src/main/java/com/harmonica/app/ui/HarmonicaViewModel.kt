package com.harmonica.app.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.harmonica.app.audio.LoudnessMonitor
import com.harmonica.app.data.ConfigClaim
import com.harmonica.app.data.GenerateRequest
import com.harmonica.app.data.HarmonicaApi
import com.harmonica.app.data.HarmonicaClient
import com.harmonica.app.data.Prefs
import com.harmonica.app.player.PlayerController
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

data class UiState(
    val connected: Boolean = false,
    val configName: String? = null,
    val baseUrl: String = "",
    val status: String = "",
    val busy: Boolean = false
)

class HarmonicaViewModel(app: Application) : AndroidViewModel(app) {

    private val prefs = Prefs(app)
    val player = PlayerController(app)
    val loudness = LoudnessMonitor(app)

    private var api: HarmonicaApi? = null
    private var baseUrl: String = ""
    private var configId: Int? = null

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state

    init {
        viewModelScope.launch {
            val savedUrl = prefs.baseUrl.first()
            val savedId = prefs.configId.first()
            val savedName = prefs.configName.first()
            if (savedUrl != null && savedId != null) {
                baseUrl = savedUrl
                configId = savedId
                api = HarmonicaClient.create(savedUrl)
                _state.value = UiState(connected = true, configName = savedName, baseUrl = savedUrl)
            }
        }
    }

    fun connect(url: String, configName: String, passphrase: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true, status = "Connecting…")
            try {
                val client = HarmonicaClient.create(url)
                val detail = client.claimConfig(ConfigClaim(configName, passphrase))
                api = client
                baseUrl = url
                configId = detail.id
                prefs.save(url, detail.id, detail.name)
                _state.value = UiState(connected = true, configName = detail.name, baseUrl = url)
            } catch (e: Exception) {
                _state.value = _state.value.copy(busy = false, status = "Couldn't connect: ${e.message}")
            }
        }
    }

    fun generate(length: Int = 50) {
        val client = api ?: return
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true, status = "Building a session…")
            try {
                loudness.refresh()
                val run = client.generate(GenerateRequest(length = length, configId = configId))
                player.load(baseUrl, run, autoPlay = true)
                _state.value = _state.value.copy(busy = false, status = "Playing ${run.items.size} tracks")
            } catch (e: Exception) {
                _state.value = _state.value.copy(busy = false, status = "Generation failed: ${e.message}")
            }
        }
    }

    fun togglePlay() = player.togglePlay()
    fun next() = player.next()
    fun previous() = player.previous()

    override fun onCleared() {
        player.release()
    }
}
