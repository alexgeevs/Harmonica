package com.harmonica.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import com.harmonica.app.ui.AppScreen
import com.harmonica.app.ui.HarmonicaViewModel
import com.harmonica.app.ui.theme.HarmonicaTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            HarmonicaTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    val vm: HarmonicaViewModel = viewModel()
                    AppScreen(vm)
                }
            }
        }
    }
}
