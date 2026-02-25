package com.musicschool.mobileapp.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun StudentScreen() {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.padding(16.dp)) {
        Text("Milestone 1: Student Core", style = MaterialTheme.typography.titleLarge)
        FeatureCard("Auth", "Login, role selection, profile sync")
        FeatureCard("Availability", "Calendar + slot list from /api/v1/student/availability")
        FeatureCard("Bookings", "Create booking + my bookings list")
        Button(onClick = { /* Hook to repository in next wiring step */ }, modifier = Modifier.fillMaxWidth()) {
            Text("Load Student Data")
        }
    }
}

@Composable
private fun FeatureCard(title: String, subtitle: String) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondary.copy(alpha = 0.18f))) {
        Column(Modifier.padding(12.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(subtitle)
        }
    }
}
