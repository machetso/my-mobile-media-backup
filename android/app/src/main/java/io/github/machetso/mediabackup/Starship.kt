package io.github.machetso.mediabackup

import android.content.Context
import android.graphics.Typeface
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.animation.core.animateFloat
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * The look of the app (user request 2026-11-19): "Starship" – the same control-panel look as the
 * desktop program (black background, rounded colour bars, an elbow frame, narrow capitals) – or
 * "Classic" (the plain Android look). Everything visual lives here; MainActivity only uses
 * [AppTheme], [Panel], [Header], [Footer], [label], [GreenSwitch] and [DisconnectButton].
 */
object Look {
    const val STARSHIP = "starship"
    const val CLASSIC = "classic"
    private const val PREFS = "ui"

    var choice by mutableStateOf(STARSHIP)
    val starship: Boolean get() = choice == STARSHIP

    /** Always Starship: the look can no longer be chosen (user request 2026-11-19, like the
     *  desktop). The classic code stays as a fallback; an old "classic" choice is ignored. */
    fun load(@Suppress("UNUSED_PARAMETER") context: Context) {
        choice = STARSHIP
    }
}

// control-panel colours – the same values as phonebackup/theme.py on the desktop
object Lcars {
    val ORANGE = Color(0xFFFF9966)
    val GOLD = Color(0xFFFFAA33)
    val PEACH = Color(0xFFFFCC99)
    val LILAC = Color(0xFFCC99CC)
    val LAVENDER = Color(0xFF9999FF)
    val BLUE = Color(0xFF99CCFF)
    val RED = Color(0xFFEE5555)
    val MAUVE = Color(0xFFCC6699)
    val GREEN = Color(0xFF77DD99)
    val BLACK = Color(0xFF000000)
    val TEXT = Color(0xFFF2DCC4)
    val DIM = Color(0xFF8A8A99)
}

/** A narrow font, as on the panels (part of every Android). */
private val narrow = FontFamily(Typeface.create("sans-serif-condensed", Typeface.NORMAL))

private fun TextStyle.narrow() = copy(fontFamily = narrow)

private val starshipType = Typography().run {
    copy(displayLarge = displayLarge.narrow(), displayMedium = displayMedium.narrow(), displaySmall = displaySmall.narrow(),
        headlineLarge = headlineLarge.narrow(), headlineMedium = headlineMedium.narrow(),
        headlineSmall = headlineSmall.narrow(), titleLarge = titleLarge.narrow(), titleMedium = titleMedium.narrow(),
        titleSmall = titleSmall.narrow(), bodyLarge = bodyLarge.narrow().copy(fontSize = 17.sp),
        bodyMedium = bodyMedium.narrow().copy(fontSize = 15.sp), bodySmall = bodySmall.narrow().copy(fontSize = 13.sp),
        labelLarge = labelLarge.narrow().copy(fontWeight = FontWeight.SemiBold, letterSpacing = 1.sp),
        labelMedium = labelMedium.narrow(), labelSmall = labelSmall.narrow())
}

private val starshipColors = darkColorScheme(
    primary = Lcars.ORANGE, onPrimary = Lcars.BLACK,
    secondary = Lcars.LILAC, onSecondary = Lcars.BLACK,
    tertiary = Lcars.LAVENDER, onTertiary = Lcars.BLACK,
    background = Lcars.BLACK, onBackground = Lcars.TEXT,
    surface = Lcars.BLACK, onSurface = Lcars.TEXT, onSurfaceVariant = Lcars.TEXT,
    surfaceContainer = Color(0xFF0B0B12), surfaceContainerHigh = Color(0xFF0B0B12),
    surfaceContainerHighest = Color(0xFF14141C), surfaceContainerLow = Color(0xFF0B0B12),
    outline = Lcars.LAVENDER, outlineVariant = Color(0xFF34344A),
    error = Lcars.RED, onError = Lcars.BLACK,
)

@Composable
fun AppTheme(content: @Composable () -> Unit) {
    if (Look.starship) MaterialTheme(colorScheme = starshipColors, typography = starshipType, content = content)
    else MaterialTheme(colorScheme = if (isSystemInDarkTheme()) darkColorScheme() else lightColorScheme(),
        content = content)
}

/** Button texts in capitals, as on the panels (only in the Starship look). */
fun label(text: String): String = if (Look.starship) text.uppercase(I18n.locale) else text

/**
 * A box of related things. Starship: a small elbow (thick bar on the side bending into a thin bar
 * on top, rounded corner) with the title in orange capitals. Classic: a card (or nothing, `card = false`).
 */
@Composable
fun Panel(title: String?, color: Color = Lcars.LILAC, card: Boolean = true, titleSize: Int = 0,
          spacing: Int = 8, content: @Composable ColumnScope.() -> Unit) {
    if (!Look.starship) {
        val inner: @Composable () -> Unit = {
            Column(Modifier.padding(if (card) 14.dp else 0.dp), verticalArrangement = Arrangement.spacedBy(spacing.dp)) {
                if (title != null) Text(title, fontWeight = FontWeight.SemiBold,
                    fontSize = if (titleSize > 0) titleSize.sp else androidx.compose.ui.unit.TextUnit.Unspecified)
                content()
            }
        }
        if (card) Card(Modifier.fillMaxWidth()) { inner() } else inner()
        return
    }
    val rtl = LocalLayoutDirection.current == LayoutDirection.Rtl
    Column(
        Modifier.fillMaxWidth().drawBehind {
            val side = 10.dp.toPx()
            val top = 4.dp.toPx()
            val r = 18.dp.toPx()
            val w = size.width
            val path = Path().apply {
                // side bar + top bar with a rounded outer corner and a small inner one
                moveTo(0f, size.height)
                lineTo(0f, r)
                quadraticTo(0f, 0f, r, 0f)
                lineTo(w, 0f)
                lineTo(w, top)
                lineTo(side + r / 2, top)
                quadraticTo(side, top, side, top + r / 2)
                lineTo(side, size.height)
                close()
            }
            if (rtl) {
                scale(-1f, 1f, pivot = center) { drawPath(path, color) }
            } else drawPath(path, color)
        }.padding(start = 22.dp, top = 12.dp, end = 4.dp, bottom = 6.dp),
        verticalArrangement = Arrangement.spacedBy(spacing.dp),
    ) {
        if (title != null) Text(title.uppercase(I18n.locale), color = Lcars.ORANGE, fontWeight = FontWeight.SemiBold,
            fontSize = if (titleSize > 0) titleSize.sp else 17.sp, letterSpacing = 1.sp)
        content()
    }
}

/** Top of the screen: the program name. Starship: in an elbow bar (orange), as on the desktop. */
@Composable
fun Header(title: String, end: (@Composable () -> Unit)? = null) {
    if (!Look.starship) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(title, fontSize = 26.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            end?.invoke()
        }
        return
    }
    val endSpace = if (end != null) 40.dp else 0.dp     // room for the globe at the end of the bar
    val rtl = LocalLayoutDirection.current == LayoutDirection.Rtl
    Box(
        Modifier.fillMaxWidth().height(78.dp).drawBehind {
            val block = 64.dp.toPx()       // width of the left block
            val bar = 22.dp.toPx()         // thickness of the top bar
            val outer = 34.dp.toPx()
            val inner = 14.dp.toPx()
            val w = size.width - endSpace.toPx()
            val h = size.height
            val elbow = Path().apply {
                moveTo(0f, h)
                lineTo(0f, outer)
                quadraticTo(0f, 0f, outer, 0f)
                lineTo(w - bar / 2, 0f)
                arcTo(Rect(w - bar, 0f, w, bar), -90f, 180f, false)   // rounded end
                lineTo(block + inner, bar)
                quadraticTo(block, bar, block, bar + inner)
                lineTo(block, h)
                close()
            }
            val draw: androidx.compose.ui.graphics.drawscope.DrawScope.() -> Unit = {
                drawPath(elbow, Lcars.ORANGE)
                // a small block of another colour at the end of the bar
                drawRoundRect(Lcars.LILAC, topLeft = Offset(w * 0.55f, 0f), size = Size(w * 0.12f, bar),
                    cornerRadius = CornerRadius.Zero)
                drawRect(Lcars.BLACK, topLeft = Offset(w * 0.55f - 4.dp.toPx(), 0f), size = Size(4.dp.toPx(), bar))
                drawRect(Lcars.BLACK, topLeft = Offset(w * 0.67f, 0f), size = Size(4.dp.toPx(), bar))
            }
            if (rtl) scale(-1f, 1f, pivot = center) { draw() } else draw()
        },
        contentAlignment = Alignment.BottomEnd,
    ) {
        Text(title.uppercase(I18n.locale), color = Lcars.ORANGE, fontSize = 28.sp, fontWeight = FontWeight.SemiBold,
            letterSpacing = 2.sp, fontFamily = narrow, modifier = Modifier.padding(start = 76.dp, bottom = 0.dp))
        if (end != null) Box(Modifier.align(Alignment.TopEnd)) { end() }
    }
}

/** A mini globe in the panel colours – the language choice, as on the computer (user request 2026-11-19). */
@Composable
fun Globe(onClick: () -> Unit) {
    Canvas(Modifier.size(34.dp).clickable(onClick = onClick).padding(2.dp)) {
        val r = size.minDimension / 2
        val c = center
        drawCircle(Lcars.LILAC, r, c)
        val line = 1.6.dp.toPx()
        drawOval(Lcars.BLACK, topLeft = Offset(c.x - r * 0.45f, c.y - r), size = Size(r * 0.9f, 2 * r),
            style = Stroke(line))
        drawLine(Lcars.BLACK, Offset(c.x, c.y - r), Offset(c.x, c.y + r), line)
        drawLine(Lcars.BLACK, Offset(c.x - r, c.y), Offset(c.x + r, c.y), line)
        for (dy in listOf(-0.5f, 0.5f)) {
            val half = r * kotlin.math.sqrt(1 - dy * dy)
            drawLine(Lcars.BLACK, Offset(c.x - half, c.y + dy * r), Offset(c.x + half, c.y + dy * r), line)
        }
    }
}

/** Bottom of the screen: a thin elbow bar (Starship only) above the version line. */
@Composable
fun Footer() {
    if (!Look.starship) return
    val rtl = LocalLayoutDirection.current == LayoutDirection.Rtl
    Box(Modifier.fillMaxWidth().height(34.dp).drawBehind {
        val block = 64.dp.toPx()
        val bar = 12.dp.toPx()
        val outer = 24.dp.toPx()
        val inner = 10.dp.toPx()
        val w = size.width
        val h = size.height
        val elbow = Path().apply {
            moveTo(0f, 0f)
            lineTo(block, 0f)
            lineTo(block, h - bar - inner)
            quadraticTo(block, h - bar, block + inner, h - bar)
            lineTo(w - bar / 2, h - bar)
            arcTo(Rect(w - bar, h - bar, w, h), -90f, 180f, false)
            lineTo(outer, h)
            quadraticTo(0f, h, 0f, h - outer)
            close()
        }
        val draw: androidx.compose.ui.graphics.drawscope.DrawScope.() -> Unit = { drawPath(elbow, Lcars.PEACH) }
        if (rtl) scale(-1f, 1f, pivot = center) { draw() } else draw()
    })
}

/**
 * Small animation while a backup runs (user request 2026-11-19): the gold arrow of the app icon with
 * a bright pulse moving inside it from the bottom to the tip. Same drawing as phonebackup/backup_anim.py.
 */
@Composable
fun BackupArrow(modifier: Modifier = Modifier) {
    val t = androidx.compose.animation.core.rememberInfiniteTransition(label = "pulse")
    val p by t.animateFloat(0f, 1f, androidx.compose.animation.core.infiniteRepeatable(
        androidx.compose.animation.core.tween(1400, easing = androidx.compose.animation.core.LinearEasing)),
        label = "p")
    val bright = if (Look.starship) Color(0xFFFFFBE6) else Color(0xFFFFF3C4)
    androidx.compose.foundation.Canvas(modifier.size(44.dp, 52.dp)) {
        val tip = -58f; val base = 36f; val band = 24f
        val y = base + band - p * (base - tip + 2 * band)          // centre of the bright band
        val s = minOf(size.width / 110f, size.height / 112f)
        val cx = size.width / 2
        val cy = size.height / 2 + 3 * s
        val arrow = Path().apply {
            val pts = listOf(0f to -58f, 40f to -14f, 16f to -14f, 16f to 36f, -16f to 36f, -16f to -14f, -40f to -14f)
            moveTo(cx + pts[0].first * s, cy + pts[0].second * s)
            pts.drop(1).forEach { (x, yy) -> lineTo(cx + x * s, cy + yy * s) }
            close()
        }
        drawPath(arrow, Lcars.GOLD)
        drawPath(arrow, androidx.compose.ui.graphics.Brush.verticalGradient(
            listOf(bright.copy(alpha = 0f), bright, bright.copy(alpha = 0f)),
            startY = cy + (y - band) * s, endY = cy + (y + band) * s))
        drawPath(arrow, Color.Black, style = androidx.compose.ui.graphics.drawscope.Stroke(6f * s,
            join = androidx.compose.ui.graphics.StrokeJoin.Round))
    }
}


// ---------------------------------------------------------------- switches and glow (2026-11-20)

object Glow {
    val GREEN_BRIGHT = Color(0xFF55FF88)     // "Fast connection" on
    val GREEN_DARK = Color(0xFF1E5631)       // … off
    val RED_BRIGHT = Color(0xFFFF4444)       // "Disconnect": something can be switched off
    val RED_DARK = Color(0xFF5A1E1E)         // … nothing to switch off
    val ON = Color(0xFF3DBE5C)               // "Allow backup" on
    val OFF = Color(0xFFD03A3A)              // … off
}

/** "Allow backup" (user requests 2026-11-20): a toggle switch, bright green when on, dark green
 *  when off – no glow. */
@Composable
fun GreenSwitch(checked: Boolean, onCheckedChange: (Boolean) -> Unit, enabled: Boolean = true) {
    androidx.compose.material3.Switch(
        checked = checked, onCheckedChange = onCheckedChange, enabled = enabled,
        modifier = Modifier.padding(6.dp),                 // no glow (user 2026-11-20)
        colors = androidx.compose.material3.SwitchDefaults.colors(
            checkedThumbColor = Color.White, checkedTrackColor = Glow.GREEN_BRIGHT,
            checkedBorderColor = Glow.GREEN_BRIGHT,
            uncheckedThumbColor = Color(0xFF9FB8A6), uncheckedTrackColor = Glow.GREEN_DARK,
            uncheckedBorderColor = Glow.GREEN_DARK))
}

/** "Disconnect" (user request 2026-11-20): bright red when there is something to switch off,
 *  darker red when there is nothing – no glow (changed the same day). */
@Composable
fun DisconnectButton(text: String, active: Boolean, onClick: () -> Unit) {
    androidx.compose.material3.Button(
        onClick = onClick, enabled = active,
        modifier = Modifier.padding(6.dp),                 // no glow (user 2026-11-20)
        colors = ButtonDefaults.buttonColors(
            containerColor = Glow.RED_BRIGHT, contentColor = Color.White,
            disabledContainerColor = Glow.RED_DARK, disabledContentColor = Color(0xFFB08080))) {
        Text(label(text))
    }
}
