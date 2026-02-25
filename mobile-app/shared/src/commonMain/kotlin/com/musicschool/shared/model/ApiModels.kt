package com.musicschool.shared.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ApiEnvelope<T>(
    val ok: Boolean,
    val data: T? = null,
    val error: String? = null,
)

@Serializable
data class LoginRequest(val email: String, val password: String)

@Serializable
data class RoleRequest(val role: String)

@Serializable
data class UserSummary(
    val id: Int,
    val email: String,
    @SerialName("full_name") val fullName: String? = null,
    val roles: List<String> = emptyList(),
    @SerialName("active_role") val activeRole: String? = null,
)

@Serializable
data class AvailabilitySlot(
    val id: Int,
    @SerialName("start_at") val startAt: String,
    @SerialName("end_at") val endAt: String,
    @SerialName("teacher_name") val teacherName: String? = null,
    @SerialName("venue_name") val venueName: String? = null,
)

@Serializable
data class BookingSummary(
    val id: Int,
    val status: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("student_name") val studentName: String? = null,
    @SerialName("teacher_name") val teacherName: String? = null,
    @SerialName("start_at") val startAt: String? = null,
    @SerialName("end_at") val endAt: String? = null,
)
