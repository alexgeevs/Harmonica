package com.harmonica.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@Composable
fun AppScreen(vm: HarmonicaViewModel) {
    val state by vm.state.collectAsState()
    Column(modifier = Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
        Text("Harmonica", style = androidx.compose.material3.MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(16.dp))
        if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (!state.connected) {
            ConnectForm(onConnect = vm::connect)
        } else {
            NowPlaying(vm)
        }
        if (state.status.isNotEmpty()) {
            Spacer(Modifier.height(12.dp))
            Text(state.status, style = androidx.compose.material3.MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun ConnectForm(onConnect: (String, String, String) -> Unit) {
    var url by remember { mutableStateOf("http://192.168.1.50:8765") }
    var name by remember { mutableStateOf("") }
    var pass by remember { mutableStateOf("") }
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        OutlinedTextField(url, { url = it }, label = { Text("Daemon URL") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(name, { name = it }, label = { Text("Config name") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(
            pass, { pass = it }, label = { Text("Passphrase") },
            visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth()
        )
        Button(onClick = { onConnect(url.trim(), name.trim(), pass) }, modifier = Modifier.fillMaxWidth()) {
            Text("Connect")
        }
    }
}

@Composable
private fun NowPlaying(vm: HarmonicaViewModel) {
    val title by vm.player.currentTitle.collectAsState()
    val isPlaying by vm.player.isPlaying.collectAsState()
    val loud by vm.loudness.state.collectAsState()
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(if (title.isEmpty()) "Nothing playing" else title)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = vm::previous) { Icon(Icons.Filled.SkipPrevious, contentDescription = "Previous") }
            IconButton(onClick = vm::togglePlay) {
                Icon(if (isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow, contentDescription = "Play/Pause")
            }
            IconButton(onClick = vm::next) { Icon(Icons.Filled.SkipNext, contentDescription = "Next") }
        }
        Button(onClick = { vm.generate() }, modifier = Modifier.fillMaxWidth()) { Text("Generate session") }
        // Hearing-health readout from real device signals (relative estimate).
        Text("Output: ${loud.outputType}  ·  Volume ${(loud.volumeFraction * 100).toInt()}%")
        LinearProgressIndicator(progress = { loud.exposure }, modifier = Modifier.fillMaxWidth())
        if (loud.exposure > 0.7f) {
            Text("Loud for your ears — consider turning it down.")
        }
    }
}
