package com.harmonica.app.data

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

/**
 * Builds a [HarmonicaApi] for a given daemon base URL (e.g. http://192.168.1.50:8765/).
 * The base URL changes per network, so the client is rebuilt when the user (re)connects.
 */
object HarmonicaClient {

    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    fun create(baseUrl: String): HarmonicaApi {
        val normalized = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        val http = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
        return Retrofit.Builder()
            .baseUrl(normalized)
            .client(http)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(HarmonicaApi::class.java)
    }

    /** Absolute URL for streaming a media asset from the daemon. */
    fun mediaUrl(baseUrl: String, mediaPath: String): String {
        val base = baseUrl.trimEnd('/')
        return if (mediaPath.startsWith("http")) mediaPath else base + mediaPath
    }
}
