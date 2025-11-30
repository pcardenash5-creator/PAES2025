import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# -------------------------------------------------------------------
#  CONFIGURACIÓN GENERAL – LOOK MINEDUC LOS LAGOS
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Dashboard PAES 2025 – SEREMI Los Lagos",
    page_icon="📊",
    layout="wide",
)

# Colores tipo MINEDUC / Región de Los Lagos
COLOR_PRIMARY = "#004B8D"      # azul oscuro
COLOR_SECONDARY = "#0072CE"    # azul claro
COLOR_ACCENT = "#00A398"       # verde agua
COLOR_BG = "#F5F7FB"           # gris muy claro

st.markdown(
    f"""
    <style>
    body {{
        background-color: {COLOR_BG};
    }}
    .main {{
        background-color: {COLOR_BG};
    }}
    h1, h2, h3, h4 {{
        color: {COLOR_PRIMARY};
        font-family: "Segoe UI", sans-serif;
    }}
    .metric-card {{
        background: linear-gradient(135deg, {COLOR_PRIMARY}, {COLOR_SECONDARY});
        padding: 14px 18px;
        border-radius: 12px;
        color: white;
        box-shadow: 0 4px 10px rgba(0,0,0,0.12);
    }}
    .metric-label {{
        font-size: 12px;
        text-transform: uppercase;
        opacity: 0.9;
        letter-spacing: 0.06em;
    }}
    .metric-value {{
        font-size: 24px;
        font-weight: 700;
        margin-top: 2px;
    }}
    .metric-sub {{
        font-size: 11px;
        margin-top: 5px;
        opacity: 0.9;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------------------------
#  CONSTANTES DE NOMBRE DE COLUMNAS
# -------------------------------------------------------------------
COL_ID = "ID Estudiante"
COL_ESTADO = "Estado Final"
COL_DEP = "Dependencia Administrativa"
COL_RAMA = "Rama Educativa"
COL_COMUNA = "Nombre Comuna"
COL_DEPROV = "Departamento Provincial"


# -------------------------------------------------------------------
#  FUNCIONES AUXILIARES
# -------------------------------------------------------------------
@st.cache_data
def cargar_datos(path: str = "PAES2025_Prueba.xlsx") -> pd.DataFrame:
    """Carga y prepara la base consolidada."""
    # Hoja principal
    df = pd.read_excel(path, sheet_name="Consolidado 1")
    df.columns = [c.strip() for c in df.columns]

    # Hoja ID Matriculado
    try:
        df_id = pd.read_excel(path, sheet_name="ID Matriculado")
        df_id.columns = [c.strip() for c in df_id.columns]
    except Exception:
        df_id = None

    # Hoja CODIGO_UNIV
    try:
        df_unis = pd.read_excel(path, sheet_name="CODIGO_UNIV")
        df_unis.columns = [c.strip() for c in df_unis.columns]
    except Exception:
        df_unis = None

    # ---------------- 1) MERGE ID → CODIGO_UNIV ----------------
    if df_id is not None and COL_ID in df.columns and "CODIGO_UNIV" in df_id.columns:
        df = df.merge(df_id[[COL_ID, "CODIGO_UNIV"]], on=COL_ID, how="left")
    else:
        st.warning("No se pudo enlazar 'ID Matriculado' (revisar hoja y columnas).")

    # ---------------- 2) MERGE CODIGO_UNIV → NOMBRE_UNIVERSIDAD ----------------
    if df_unis is not None:
        # Buscamos columnas equivalentes
        posibles_cod = ["UNI_CODIGO", "CODIGO_UNIV"]
        posibles_nom = ["NOMBRE_UNIVERSIDAD", "Nombre_Universidad"]

        col_cod = next((c for c in posibles_cod if c in df_unis.columns), None)
        col_nom = next((c for c in posibles_nom if c in df_unis.columns), None)

        if col_cod and col_nom and "CODIGO_UNIV" in df.columns:
            unis_simpl = df_unis[[col_cod, col_nom]].drop_duplicates(col_cod)
            df = df.merge(
                unis_simpl,
                left_on="CODIGO_UNIV",
                right_on=col_cod,
                how="left",
            )
            if "NOMBRE_UNIVERSIDAD" not in df.columns:
                df = df.rename(columns={col_nom: "NOMBRE_UNIVERSIDAD"})
        else:
            st.warning(
                "No se encontraron columnas claras de código / nombre de universidad "
                "en 'CODIGO_UNIV'. Ranking de universidades limitado."
            )

    # ---------------- 3) VARIABLE DE MATRÍCULA ----------------
    if COL_ESTADO in df.columns:
        df["ES_MATRICULADO"] = np.where(df[COL_ESTADO].astype(str).str.upper() == "MATRICULADO", 1, 0)
    else:
        df["ES_MATRICULADO"] = np.where(df.get("CODIGO_UNIV").notna(), 1, 0)

    # Limpiamos textos clave
    for col in [COL_DEP, COL_RAMA, COL_COMUNA, COL_DEPROV, "NOMBRE_UNIVERSIDAD"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df


def metric_card_html(label: str, value: str, sub: str = "") -> str:
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-sub">{sub}</div>
    </div>
    """


def estilo_tabla(df_tabla: pd.DataFrame):
    """Estilo limpio sin usar matplotlib (compatibilidad total)."""
    num_cols = df_tabla.select_dtypes(include=[np.number]).columns

    styler = (
        df_tabla
        .style
        .format({c: "{:,.0f}".format for c in num_cols})
        .set_properties(
            **{
                "border": "1px solid #D0D7E2",
                "font-size": "13px",
                "font-family": "Segoe UI, sans-serif",
                "background-color": "#FFFFFF",
            }
        )
        .set_table_styles(
            [
                {
                    "selector": "th",
                    "props": [
                        ("background-color", "#DBE4F0"),
                        ("color", "#000000"),
                        ("font-weight", "bold"),
                        ("border", "1px solid #A4B3C5"),
                    ],
                },
                {
                    "selector": "tbody tr:nth-child(even)",
                    "props": [("background-color", "#F3F6FB")],
                },
            ]
        )
    )
    return styler


def tabla_deprov_dependencia(df: pd.DataFrame) -> pd.DataFrame:
    """Tabla tipo Excel: DEPROV x Dependencia x Estado + Totales."""
    base = df.copy()

    tabla = (
        base
        .groupby([COL_DEPROV, COL_DEP, COL_ESTADO])[COL_ID]
        .count()
        .reset_index(name="N")
    )

    pivot = tabla.pivot_table(
        index=COL_DEPROV,
        columns=[COL_DEP, COL_ESTADO],
        values="N",
        fill_value=0,
        aggfunc="sum",
    )

    # Totales por dependencia
    for dep in sorted(base[COL_DEP].dropna().unique()):
        if dep in pivot.columns.get_level_values(0):
            sub = pivot.xs(dep, level=0, axis=1)
            pivot[(dep, "Total")] = sub.sum(axis=1)

    # Total general
    pivot[("Total", "General")] = pivot.sum(axis=1)

    # Fila regional
    total_reg = pivot.sum(axis=0)
    pivot.loc["Total Regional"] = total_reg

    # Aplanar columnas
    pivot.columns = [f"{dep} - {estado}" for dep, estado in pivot.columns]

    pivot = pivot.reset_index().rename(columns={COL_DEPROV: "DEPROV"})

    return pivot


def ranking_matriculados(df: pd.DataFrame, group_cols, nombre_grupo: str) -> pd.DataFrame:
    """Ranking por grupo (comuna, dependencia, universidad...)."""
    base = df[df["ES_MATRICULADO"] == 1].copy()
    if base.empty:
        return pd.DataFrame()

    tabla = (
        base
        .groupby(group_cols)[COL_ID]
        .count()
        .reset_index(name="N Matriculados")
    )

    total = tabla["N Matriculados"].sum()
    tabla["% Matriculados"] = (tabla["N Matriculados"] / total * 100).round(1)

    tabla = tabla.sort_values("N Matriculados", ascending=False)

    if isinstance(group_cols, list) and len(group_cols) == 1:
        tabla = tabla.rename(columns={group_cols[0]: nombre_grupo})
    elif not isinstance(group_cols, list):
        tabla = tabla.rename(columns={group_cols: nombre_grupo})

    return tabla


# -------------------------------------------------------------------
#  CARGA DE DATOS
# -------------------------------------------------------------------
df = cargar_datos()

st.title("📊 Dashboard PAES 2025 – Continuidad de Estudios")
st.caption("SEREMI de Educación Región de Los Lagos – Seguimiento de matrícula universitaria post PAES")

# -------------------------------------------------------------------
#  SIDEBAR – FILTROS
# -------------------------------------------------------------------
st.sidebar.header("🎛 Filtros")

deprov_opts = sorted(df[COL_DEPROV].dropna().unique())
dep_opts = sorted(df[COL_DEP].dropna().unique())
rama_opts = sorted(df[COL_RAMA].dropna().unique())

deprov_sel = st.sidebar.multiselect("Departamento Provincial", deprov_opts, default=deprov_opts)
dep_sel = st.sidebar.multiselect("Dependencia Administrativa", dep_opts, default=dep_opts)
rama_sel = st.sidebar.multiselect("Rama Educativa", rama_opts, default=rama_opts)
solo_matriculados = st.sidebar.checkbox("Ver solo estudiantes matriculados", value=False)
top_n = st.sidebar.slider("N° máximo en rankings", 5, 50, 20)

filtro = (
    df[COL_DEPROV].isin(deprov_sel)
    & df[COL_DEP].isin(dep_sel)
    & df[COL_RAMA].isin(rama_sel)
)

df_f = df[filtro].copy()
if solo_matriculados:
    df_f = df_f[df_f["ES_MATRICULADO"] == 1]

if df_f.empty:
    st.warning("⚠ No hay datos para la combinación de filtros seleccionada.")
    st.stop()

# -------------------------------------------------------------------
#  TARJETAS KPI
# -------------------------------------------------------------------
total_est = len(df_f)
total_mat = int(df_f["ES_MATRICULADO"].sum())
tasa_mat = (total_mat / total_est * 100) if total_est > 0 else 0
n_unis = int(df_f.loc[df_f["ES_MATRICULADO"] == 1, "NOMBRE_UNIVERSIDAD"].nunique()) \
    if "NOMBRE_UNIVERSIDAD" in df_f.columns else 0
n_comunas = df_f[COL_COMUNA].nunique()

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(
        metric_card_html("Total estudiantes", f"{total_est:,}", "Consolidado según filtros"),
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        metric_card_html(
            "Estudiantes matriculados",
            f"{total_mat:,}",
            f"Tasa de matrícula: {tasa_mat:.1f} %",
        ),
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        metric_card_html(
            "Universidades de destino",
            f"{n_unis:,}",
            "Distintas instituciones receptoras",
        ),
        unsafe_allow_html=True,
    )

with c4:
    st.markdown(
        metric_card_html(
            "Cobertura territorial",
            f"{n_comunas} comunas",
            "Región de Los Lagos",
        ),
        unsafe_allow_html=True,
    )

st.markdown("---")

# -------------------------------------------------------------------
#  TABS
# -------------------------------------------------------------------
tab_resumen, tab_deprov, tab_comuna, tab_dep, tab_unis = st.tabs(
    [
        "📍 Resumen regional",
        "🏛 DEPROV / Dependencia",
        "🗺 Ranking por comuna",
        "🏫 Ranking por dependencia",
        "🎓 Ranking de universidades",
    ]
)

# ---------------- TAB RESUMEN ----------------
with tab_resumen:
    st.subheader("Visión general de la matrícula")

    col_a, col_b = st.columns(2)

    # Dependencia vs Estado
    with col_a:
        tabla_dep = (
            df_f
            .groupby([COL_DEP, COL_ESTADO])[COL_ID]
            .count()
            .reset_index(name="N")
        )
        fig_dep = px.bar(
            tabla_dep,
            x=COL_DEP,
            y="N",
            color=COL_ESTADO,
            barmode="group",
            color_discrete_sequence=[COLOR_PRIMARY, COLOR_ACCENT],
            labels={COL_DEP: "Dependencia", "N": "Nº estudiantes", COL_ESTADO: "Estado"},
        )
        fig_dep.update_layout(
            title="Distribución por dependencia administrativa",
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_dep, use_container_width=True)

    # Rama vs Estado
    with col_b:
        tabla_rama = (
            df_f
            .groupby([COL_RAMA, COL_ESTADO])[COL_ID]
            .count()
            .reset_index(name="N")
        )
        fig_rama = px.bar(
            tabla_rama,
            x=COL_RAMA,
            y="N",
            color=COL_ESTADO,
            barmode="group",
            color_discrete_sequence=[COLOR_PRIMARY, COLOR_ACCENT],
            labels={COL_RAMA: "Rama educativa", "N": "Nº estudiantes", COL_ESTADO: "Estado"},
        )
        fig_rama.update_layout(
            title="Distribución por rama educativa",
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_rama, use_container_width=True)

    st.markdown("### Distribución por Departamento Provincial")

    tabla_deprov = (
        df_f
        .groupby([COL_DEPROV, COL_ESTADO])[COL_ID]
        .count()
        .reset_index(name="N")
    )
    fig_deprov = px.bar(
        tabla_deprov,
        x=COL_DEPROV,
        y="N",
        color=COL_ESTADO,
        barmode="group",
        color_discrete_sequence=[COLOR_PRIMARY, COLOR_ACCENT],
        labels={COL_DEPROV: "DEPROV", "N": "Nº estudiantes", COL_ESTADO: "Estado"},
    )
    fig_deprov.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    st.plotly_chart(fig_deprov, use_container_width=True)

# ---------------- TAB DEPROV / DEPENDENCIA ----------------
with tab_deprov:
    st.subheader("Tabla resumen por DEPROV y dependencia administrativa")
    tabla = tabla_deprov_dependencia(df_f)
    st.dataframe(estilo_tabla(tabla), use_container_width=True)

# ---------------- TAB COMUNA ----------------
with tab_comuna:
    st.subheader("Ranking de comunas (solo matriculados)")
    rk_comuna = ranking_matriculados(
        df_f,
        group_cols=[COL_DEPROV, COL_COMUNA],
        nombre_grupo="Comuna",
    )
    if rk_comuna.empty:
        st.info("No hay estudiantes matriculados para los filtros actuales.")
    else:
        rk_comuna = rk_comuna.head(top_n)
        st.dataframe(estilo_tabla(rk_comuna), use_container_width=True)

        fig = px.bar(
            rk_comuna,
            x="N Matriculados",
            y=COL_COMUNA,
            color=COL_DEPROV,
            orientation="h",
            color_discrete_sequence=px.colors.qualitative.Set2,
            labels={"N Matriculados": "Nº matriculados", COL_COMUNA: "Comuna"},
        )
        fig.update_layout(
            title="Comunas con mayor número de matriculados",
            plot_bgcolor="white",
            paper_bgcolor="white",
            yaxis={"categoryorder": "total ascending"},
        )
        st.plotly_chart(fig, use_container_width=True)

# ---------------- TAB DEPENDENCIA ----------------
with tab_dep:
    st.subheader("Ranking por dependencia administrativa")
    rk_dep = ranking_matriculados(df_f, group_cols=COL_DEP, nombre_grupo="Dependencia")
    if rk_dep.empty:
        st.info("No hay estudiantes matriculados para los filtros actuales.")
    else:
        st.dataframe(estilo_tabla(rk_dep), use_container_width=True)

        fig_dep_rank = px.bar(
            rk_dep,
            x="Dependencia",
            y="N Matriculados",
            color="Dependencia",
            color_discrete_sequence=px.colors.qualitative.Set3,
            labels={"N Matriculados": "Nº matriculados"},
        )
        fig_dep_rank.update_layout(
            title="Matrícula por tipo de dependencia",
            plot_bgcolor="white",
            paper_bgcolor="white",
            showlegend=False,
        )
        st.plotly_chart(fig_dep_rank, use_container_width=True)

# ---------------- TAB UNIVERSIDADES ----------------
with tab_unis:
    st.subheader("Ranking de universidades (solo matriculados)")
    if "NOMBRE_UNIVERSIDAD" not in df_f.columns:
        st.info(
            "No se encontró la columna 'NOMBRE_UNIVERSIDAD'. "
            "Revisa la hoja 'CODIGO_UNIV' del Excel."
        )
    else:
        rk_uni = ranking_matriculados(
            df_f,
            group_cols="NOMBRE_UNIVERSIDAD",
            nombre_grupo="Universidad",
        )
        if rk_uni.empty:
            st.info("No hay estudiantes matriculados hacia universidades.")
        else:
            rk_uni = rk_uni.head(top_n)
            st.dataframe(estilo_tabla(rk_uni), use_container_width=True)

            fig_uni = px.bar(
                rk_uni,
                x="N Matriculados",
                y="Universidad",
                orientation="h",
                color="Universidad",
                color_discrete_sequence=px.colors.qualitative.Set3,
                labels={"N Matriculados": "Nº matriculados"},
            )
            fig_uni.update_layout(
                title="Universidades con mayor número de matriculados",
                plot_bgcolor="white",
                paper_bgcolor="white",
                showlegend=False,
                yaxis={"categoryorder": "total ascending"},
            )
            st.plotly_chart(fig_uni, use_container_width=True)
