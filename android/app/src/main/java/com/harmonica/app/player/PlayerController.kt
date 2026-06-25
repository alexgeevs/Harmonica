package com.harmonica.app.player

import android.content.Context
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import com.harmonica.app.data.HarmonicaClient
import com.harmonica.app.data.QueueRun
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** Thin Media3/ExoPlayer wrapper that streams the generated queue from the daemon. */
class PlayerController(context: Context) {

    val player: ExoPlayer = ExoPlayer.Builder(context).build()

    private val _currentTitle = MutableStateFlow("")
    val currentTitle: StateFlow<String> = _currentTitle

    private val _isPlaying = MutableStateFlow(false)
    val isPlaying: StateFlow<Boolean> = _isPlaying

    init {
        player.addListener(object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                _isPlaying.value = isPlaying
            }

            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                _currentTitle.value = mediaItem?.mediaMetadata?.title?.toString() ?: ""
            }
        })
    }

    fun load(baseUrl: String, queue: QueueRun, autoPlay: Boolean) {
        val items = queue.items.mapNotNull { item ->
            val path = item.mediaUrl ?: return@mapNotNull null
            MediaItem.Builder()
                .setUri(HarmonicaClient.mediaUrl(baseUrl, path))
                .setMediaMetadata(
                    MediaMetadata.Builder()
                        .setTitle(item.track.title)
                        .setArtist(item.track.artist ?: "")
                        .build()
                )
                .build()
        }
        player.setMediaItems(items)
        player.prepare()
        player.playWhenReady = autoPlay
    }

    fun togglePlay() {
        if (player.isPlaying) player.pause() else player.play()
    }

    fun next() = player.seekToNextMediaItem()
    fun previous() = player.seekToPreviousMediaItem()

    fun release() = player.release()
}
