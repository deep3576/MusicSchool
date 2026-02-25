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
fun AdminScreen() {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.padding(16.dp)) {
        Text("Milestone 3: Admin Core", style = MaterialTheme.typography.titleLarge)
        AdminCard("Messages", "Threads + replies")
        AdminCard("Teachers/Venues", "Manage staff, slots, venues")
        AdminCard("Users/Bookings", "Roles, credits, booking actions")
        Button(onClick = {}, modifier = Modifier.fillMaxWidth()) {
            Text("Refresh Admin Dashboard")
        }
    }
}

@Composable
private fun AdminCard(title: String, subtitle: String) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiary.copy(alpha = 0.12f))) {
        Column(Modifier.padding(12.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(subtitle)
        }
    }
}
