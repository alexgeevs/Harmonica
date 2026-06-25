package com.harmonica.app.data

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

/** The subset of the Harmonica daemon API the Android client uses. */
interface HarmonicaApi {

    @GET("health")
    suspend fun health(): Map<String, String>

    @POST("configs/claim")
    suspend fun claimConfig(@Body claim: ConfigClaim): ConfigDetail

    @GET("tracks")
    suspend fun tracks(): List<Track>

    @POST("queue/generate")
    suspend fun generate(@Body request: GenerateRequest): QueueRun

    @POST("playback-events")
    suspend fun recordEvent(@Body event: PlaybackEvent)
}
