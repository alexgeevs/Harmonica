package com.harmonica.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

val Context.dataStore by preferencesDataStore(name = "harmonica")

/** Remembers the daemon URL and the claimed config so the device reconnects after IP changes. */
class Prefs(private val context: Context) {
    private val baseUrlKey = stringPreferencesKey("base_url")
    private val configIdKey = intPreferencesKey("config_id")
    private val configNameKey = stringPreferencesKey("config_name")

    val baseUrl: Flow<String?> = context.dataStore.data.map { it[baseUrlKey] }
    val configId: Flow<Int?> = context.dataStore.data.map { it[configIdKey] }
    val configName: Flow<String?> = context.dataStore.data.map { it[configNameKey] }

    suspend fun save(baseUrl: String, configId: Int, configName: String) {
        context.dataStore.edit {
            it[baseUrlKey] = baseUrl
            it[configIdKey] = configId
            it[configNameKey] = configName
        }
    }
}
