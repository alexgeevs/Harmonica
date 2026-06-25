package com.harmonica.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Mirrors the daemon JSON. Only the fields the app uses are modelled. */

@Serializable
data class MediaAsset(
    val id: Int,
    @SerialName("asset_type") val assetType: String,
    @SerialName("is_lossless") val isLossless: Boolean? = null
)

@Serializable
data class Track(
    val id: Int,
    val title: String,
    val artist: String? = null,
    val album: String? = null,
    @SerialName("audio_only") val audioOnly: Boolean = false,
    val assets: List<MediaAsset> = emptyList()
)

@Serializable
data class QueueItem(
    val position: Int,
    val track: Track,
    @SerialName("media_asset_id") val mediaAssetId: Int? = null,
    @SerialName("media_url") val mediaUrl: String? = null,
    val score: Double = 0.0
)

@Serializable
data class QueueRun(
    val id: Int,
    val length: Int,
    val items: List<QueueItem> = emptyList()
)

@Serializable
data class ConfigClaim(val name: String, val passphrase: String)

@Serializable
data class ConfigDetail(
    val id: Int,
    val name: String,
    @SerialName("included_track_ids") val includedTrackIds: List<Int> = emptyList()
)

@Serializable
data class GenerateRequest(
    val length: Int,
    @SerialName("ui_active") val uiActive: Boolean = true,
    @SerialName("config_id") val configId: Int? = null
)

@Serializable
data class PlaybackEvent(
    @SerialName("event_type") val eventType: String,
    @SerialName("track_id") val trackId: Int,
    @SerialName("media_asset_id") val mediaAssetId: Int? = null,
    @SerialName("playlist_run_id") val playlistRunId: Int? = null,
    @SerialName("queue_position") val queuePosition: Int? = null,
    @SerialName("progress_seconds") val progressSeconds: Double? = null,
    @SerialName("duration_seconds") val durationSeconds: Double? = null,
    @SerialName("output_gain") val outputGain: Double? = null
)
