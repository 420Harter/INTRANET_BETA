import os
import ssl  # <--- ¡IMPORTANTE! Agrega esta importación aquí arriba
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)
app.secret_key = 'intranet_secret_key_database_course'

# Configuración de conexión a tu TiDB Cloud
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Forzamos la encriptación segura usando el contexto nativo de Python
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "connect_args": {
        "ssl": ssl.create_default_context()  # <--- Cambiamos `{}` por esto
    }
}

db = SQLAlchemy(app)

# Variable global definida según los registros de tus periodos académicos
PERIODO_ACTUAL = 2  # Ajustar al ID correspondiente en tu tabla Periodo_Academico (ej: 2026-I)

# =========================================
# 1. SISTEMA DE LOGIN & AUTENTICACIÓN
# =========================================
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        contraseña = request.form['contraseña']
        
        try:
            query = text("""
                SELECT U.USUARIO, U.TIPO, U.COD_ALU_FK,
                       A.NOMBRES, A.APELLIDO_PATERNO, A.APELLIDO_MATERNO
                FROM Usuarios U
                LEFT JOIN Alumnos A ON U.COD_ALU_FK = A.COD_ALU
                WHERE U.USUARIO = :usuario AND U.CONTRASEÑA = :contraseña
            """)
            
            result = db.session.execute(query, {'usuario': usuario, 'contraseña': contraseña})
            user = result.fetchone()
            
            if user:
                session['usuario'] = user.USUARIO
                session['tipo'] = user.TIPO
                session['cod_alu'] = user.COD_ALU_FK
                session['nombre'] = f"{user.NOMBRES} {user.APELLIDO_PATERNO} {user.APELLIDO_MATERNO}"
                
                if user.TIPO == 'ALUMNO':
                    return redirect(url_for('alumno_dashboard'))
                else:
                    return redirect(url_for('admin_dashboard'))
            else:
                flash('Usuario o contraseña incorrectos', 'error')
                
        except Exception as e:
            flash(f'Error en el servidor: {str(e)}', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# =========================================
# 2. VISTAS Y FUNCIONES DEL ALUMNO
# =========================================
@app.route('/alumno/dashboard')
def alumno_dashboard():
    if 'usuario' not in session or session['tipo'] != 'ALUMNO':
        return redirect(url_for('login'))
        
    try:
        # Se obtienen los cursos matriculados usando la función auxiliar
        cursos_lista = obtener_cursos_matriculados(session['cod_alu'])
        return render_template('alumno_dashboard.html', nombre=session['nombre'], cod_alu=session['cod_alu'], cursos=cursos_lista)
    except Exception as e:
        return f"Error al cargar el dashboard: {str(e)}"

@app.route('/alumno/horario')
def horario():
    if 'usuario' not in session or session['tipo'] != 'ALUMNO':
        return redirect(url_for('login'))
        
    try:
        # Consulta adaptada al script.sql real:
        # Matriculas se conecta directamente con Cursos, Seccion y Programacion_Horario
        query = text("""
            SELECT
                C.COD_CURSO,
                C.NOMBRE_CURSO,
                M.COD_SEC_FK,
                PH.DIA_SEMANA,
                PH.HORA_INICIO,
                PH.HORA_FIN,
                PH.COD_AULA_FK,
                COALESCE(P.NOMBRES, 'Por asignar') AS DOCENTE
            FROM Matriculas M
            INNER JOIN Cursos C 
                ON M.COD_CURSO_FK = C.COD_CURSO
            INNER JOIN Programacion_Horario PH 
                ON M.COD_CURSO_FK = PH.COD_CURSO_FK 
                AND M.COD_SEC_FK = PH.COD_SEC_FK
            LEFT JOIN Curso_Programado CP 
                ON M.COD_CURSO_FK = CP.COD_CURSO_FK
                AND M.COD_SEC_FK = CP.COD_SEC_FK
                AND M.ID_PERIODO_FK = CP.ID_PERIODO_FK
            LEFT JOIN Profesores P 
                ON CP.ID_PROFESOR_FK = P.ID_PROFESOR
            WHERE M.COD_ALU_FK = :cod_alu 
            AND M.ID_PERIODO_FK = :periodo 
            ORDER BY
                CASE UPPER(PH.DIA_SEMANA) 
                    WHEN 'LUNES'     THEN 1
                    WHEN 'MARTES'    THEN 2
                    WHEN 'MIERCOLES' THEN 3
                    WHEN 'MIÉRCOLES' THEN 3
                    WHEN 'JUEVES'    THEN 4
                    WHEN 'VIERNES'   THEN 5
                    WHEN 'SABADO'    THEN 6
                    WHEN 'SÁBADO'    THEN 6
                    ELSE 7
                END,
                PH.HORA_INICIO;
        """)
        
        result = db.session.execute(query, {
            'cod_alu': session['cod_alu'],
            'periodo': PERIODO_ACTUAL
        })
        horario_lista = result.fetchall()
        
        return render_template('horario.html', horario=horario_lista)
        
    except Exception as e:
        return f"Error al procesar el horario: {str(e)}"


def obtener_cursos_matriculados(cod_alu):
    try:
        # Consulta adaptada al script.sql real para el listado del Perfil
        query = text("""
            SELECT
                C.COD_CURSO,
                C.NOMBRE_CURSO,
                M.COD_SEC_FK as SECCION,
                C.CREDITOS,
                COALESCE(P.NOMBRES, 'Por asignar') as DOCENTE
            FROM Matriculas M
            INNER JOIN Cursos C ON M.COD_CURSO_FK = C.COD_CURSO
            LEFT JOIN Curso_Programado CP ON M.COD_CURSO_FK = CP.COD_CURSO_FK
                                         AND M.COD_SEC_FK = CP.COD_SEC_FK
                                         AND M.ID_PERIODO_FK = CP.ID_PERIODO_FK
            LEFT JOIN Profesores P ON CP.ID_PROFESOR_FK = P.ID_PROFESOR
            WHERE M.COD_ALU_FK = :cod_alu
              AND M.ID_PERIODO_FK = :periodo
              #AND M.APLAZADO = 0 (FALTA CORREGIR EL NULL)
            ORDER BY C.NOMBRE_CURSO
        """)
        
        result = db.session.execute(query, {
            'cod_alu': session['cod_alu'],
            'periodo': PERIODO_ACTUAL
        })
        return result.fetchall()
    except Exception as e:
        print(f"Error al obtener cursos: {str(e)}")
        return []

# =========================================
# 3. MÓDULO ADMINISTRATIVO / DOCENTE
# =========================================
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'usuario' not in session or session['tipo'] != 'ADMIN':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html', nombre=session['nombre'])

@app.route('/admin/horarios_cursos')
def admin_horarios_cursos():
    if 'usuario' not in session or session['tipo'] != 'ADMIN':
        return redirect(url_for('login'))
        
    ciclo = request.args.get('ciclo')
    seccion = request.args.get('seccion')
    
    if not ciclo or not seccion:
        return render_template('horarios_ciclo.html', horarios=[])
        
    try:
        query = text("""
            SELECT
                C.NOMBRE_CURSO,
                PH.DIA_SEMANA,
                PH.HORA_INICIO,
                PH.HORA_FIN,
                PH.COD_AULA_FK,
                CP.COD_SEC_FK,
                COALESCE(P.NOMBRES, 'Por asignar') AS DOCENTE
            FROM Programacion_Horario PH
            INNER JOIN Curso_Programado CP 
                ON PH.COD_CURSO_FK = CP.COD_CURSO_FK
                AND PH.COD_SEC_FK = CP.COD_SEC_FK 
                -- AND PH.ID_PERIODO_FK = CP.ID_PERIODO_FK (AGREGAR PERIODO EN HTML)
            INNER JOIN Cursos C 
                ON CP.COD_CURSO_FK = C.COD_CURSO
            LEFT JOIN Profesores P 
                ON CP.ID_PROFESOR_FK = P.ID_PROFESOR
            WHERE C.CICLO = :ciclo
            AND CP.COD_SEC_FK = :seccion
            AND CP.ID_PERIODO_FK = :periodo
            ORDER BY
                CASE UPPER(PH.DIA_SEMANA)
                    WHEN 'LUNES'     THEN 1
                    WHEN 'MARTES'    THEN 2
                    WHEN 'MIERCOLES' THEN 3
                    WHEN 'MIÉRCOLES' THEN 3
                    WHEN 'JUEVES'    THEN 4
                    WHEN 'VIERNES'   THEN 5
                    WHEN 'SABADO'    THEN 6
                    WHEN 'SÁBADO'    THEN 6
                    ELSE 7
                END,
                PH.HORA_INICIO;
        """)
        
        result = db.session.execute(query, {
            'ciclo': ciclo,
            'seccion': seccion,
            'periodo': PERIODO_ACTUAL
        })
        horarios = result.fetchall()
        
        return render_template('horarios_ciclo.html', horarios=horarios, ciclo=ciclo, seccion=seccion)
        
    except Exception as e:
        return f"Error al consultar horarios por ciclo: {str(e)}"

@app.route('/admin/alumnos_matriculados')
def admin_alumnos_matriculados():
    if 'usuario' not in session or session['tipo'] != 'ADMIN':
        return redirect(url_for('login'))
        
    periodo = request.args.get('periodo', PERIODO_ACTUAL)
    
    try:
        query = text("""
            SELECT
                A.COD_ALU,
                A.NOMBRES,
                A.APELLIDO_PATERNO,
                A.APELLIDO_MATERNO,
                C.NOMBRE_CURSO,
                C.COD_CURSO,
                M.COD_SEC_FK as SECCION,
                C.CREDITOS
            FROM Matriculas M
            INNER JOIN Alumnos A ON M.COD_ALU_FK = A.COD_ALU
            INNER JOIN Cursos C ON M.COD_CURSO_FK = C.COD_CURSO
            WHERE M.ID_PERIODO_FK = :periodo
                AND M.APLAZADO = 0
            ORDER BY A.COD_ALU, C.NOMBRE_CURSO
        """)
        
        result = db.session.execute(query, {'periodo': periodo})
        alumnos = result.fetchall()
        
        return render_template('alumnos_matriculados.html', alumnos=alumnos, periodo=periodo)
        
    except Exception as e:
        return f"Error al listar alumnos matriculados: {str(e)}"

@app.route('/admin/horario_profesor')
def admin_horario_profesor():
    if 'usuario' not in session or session['tipo'] != 'ADMIN':
        return redirect(url_for('login'))
        
    prof_id = request.args.get('profesor')
    
    if not prof_id:
        return render_template('horario_profesor.html', horarios=[])
        
    try:
        query = text("""
            SELECT
                P.NOMBRES AS PROFESOR,
                C.NOMBRE_CURSO,
                CP.COD_SEC_FK AS SECCION,
                PH.DIA_SEMANA,
                PH.HORA_INICIO,
                PH.HORA_FIN,
                PH.COD_AULA_FK
            FROM Curso_Programado CP
            INNER JOIN Profesores P ON CP.ID_PROFESOR_FK = P.ID_PROFESOR
            INNER JOIN Cursos C ON CP.COD_CURSO_FK = C.COD_CURSO
            INNER JOIN Programacion_Horario PH ON CP.COD_CURSO_FK = PH.COD_CURSO_FK
                AND CP.COD_SEC_FK = PH.COD_SEC_FK
                -- AND CP.ID_PERIODO_FK = PH.ID_PERIODO_FK(MANEJADO CON PERIODOS-AGREGAR EN HTML)
            WHERE CP.ID_PROFESOR_FK = '02C'
            AND CP.ID_PERIODO_FK = 2
            ORDER BY
                CASE UPPER(PH.DIA_SEMANA)
                    WHEN 'LUNES'     THEN 1
                    WHEN 'MARTES'    THEN 2
                    WHEN 'MIERCOLES' THEN 3
                    WHEN 'JUEVES'    THEN 4
                    WHEN 'VIERNES'   THEN 5
                    WHEN 'SABADO'    THEN 6
                    ELSE 7
                END,
                PH.HORA_INICIO;
        """)
        
        result = db.session.execute(query, {
            'prof_id': prof_id,
            'periodo': PERIODO_ACTUAL
        })
        horarios_prof = result.fetchall()
        
        return render_template('horario_profesor.html', horarios=horarios_prof, prof_id=prof_id)
        
    except Exception as e:
        return f"Error al obtener el horario del docente: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True, port=5000)
