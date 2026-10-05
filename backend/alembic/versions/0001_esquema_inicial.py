"""esquema inicial

Revision ID: 0001
Revises: 
Create Date: 2026-10-04 20:20:30.950836

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea usuarios, consultas, correcciones y usos_llm."""
    
    op.create_table('usuarios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=200), nullable=False),
    sa.Column('nombre', sa.String(length=120), nullable=False),
    sa.Column('hash_password', sa.String(length=200), nullable=False),
    sa.Column('rol', sa.String(length=20), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_usuarios_email'), 'usuarios', ['email'], unique=True)
    op.create_table('consultas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('canal', sa.String(length=20), nullable=False),
    sa.Column('id_externo', sa.String(length=300), nullable=True),
    sa.Column('remitente_nombre', sa.String(length=150), nullable=True),
    sa.Column('remitente_email', sa.String(length=200), nullable=False),
    sa.Column('asunto', sa.String(length=300), nullable=False),
    sa.Column('cuerpo', sa.Text(), nullable=False),
    sa.Column('recibida_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('estado', sa.String(length=20), nullable=False),
    sa.Column('categoria', sa.String(length=40), nullable=True),
    sa.Column('urgencia', sa.String(length=20), nullable=True),
    sa.Column('sentimiento', sa.String(length=20), nullable=True),
    sa.Column('resumen', sa.Text(), nullable=True),
    sa.Column('datos_extraidos', postgresql.JSONB(), nullable=True),
    sa.Column('borrador_respuesta', sa.Text(), nullable=True),
    sa.Column('confianza', sa.Numeric(precision=4, scale=3), nullable=True),
    sa.Column('categoria_modelo', sa.String(length=40), nullable=True),
    sa.Column('urgencia_modelo', sa.String(length=20), nullable=True),
    sa.Column('clasificador', sa.String(length=80), nullable=True),
    sa.Column('area_asignada', sa.String(length=60), nullable=True),
    sa.Column('sla_vence_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reglas_aplicadas', postgresql.JSONB(), nullable=True),
    sa.Column('respuesta_final', sa.Text(), nullable=True),
    sa.Column('revisada_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('aprobada_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('aprobada_por_id', sa.Integer(), nullable=True),
    sa.Column('intentos', sa.Integer(), nullable=False),
    sa.Column('error_detalle', sa.Text(), nullable=True),
    sa.Column('clasificada_en', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['aprobada_por_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id_externo')
    )
    op.create_index(op.f('ix_consultas_area_asignada'), 'consultas', ['area_asignada'], unique=False)
    op.create_index(op.f('ix_consultas_categoria'), 'consultas', ['categoria'], unique=False)
    op.create_index(op.f('ix_consultas_estado'), 'consultas', ['estado'], unique=False)
    op.create_index(op.f('ix_consultas_recibida_en'), 'consultas', ['recibida_en'], unique=False)
    op.create_index(op.f('ix_consultas_urgencia'), 'consultas', ['urgencia'], unique=False)
    op.create_table('correcciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('consulta_id', sa.Integer(), nullable=False),
    sa.Column('campo', sa.String(length=30), nullable=False),
    sa.Column('valor_anterior', sa.String(length=60), nullable=True),
    sa.Column('valor_nuevo', sa.String(length=60), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('creada_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['consulta_id'], ['consultas.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_correcciones_consulta_id'), 'correcciones', ['consulta_id'], unique=False)
    op.create_table('usos_llm',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('consulta_id', sa.Integer(), nullable=True),
    sa.Column('modelo', sa.String(length=80), nullable=False),
    sa.Column('tokens_entrada', sa.Integer(), nullable=False),
    sa.Column('tokens_salida', sa.Integer(), nullable=False),
    sa.Column('costo_usd', sa.Numeric(precision=12, scale=6), nullable=False),
    sa.Column('duracion_ms', sa.Integer(), nullable=False),
    sa.Column('intentos', sa.Integer(), nullable=False),
    sa.Column('exito', sa.Boolean(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['consulta_id'], ['consultas.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_usos_llm_consulta_id'), 'usos_llm', ['consulta_id'], unique=False)
    


def downgrade() -> None:
    """Downgrade schema."""
    
    op.drop_index(op.f('ix_usos_llm_consulta_id'), table_name='usos_llm')
    op.drop_table('usos_llm')
    op.drop_index(op.f('ix_correcciones_consulta_id'), table_name='correcciones')
    op.drop_table('correcciones')
    op.drop_index(op.f('ix_consultas_urgencia'), table_name='consultas')
    op.drop_index(op.f('ix_consultas_recibida_en'), table_name='consultas')
    op.drop_index(op.f('ix_consultas_estado'), table_name='consultas')
    op.drop_index(op.f('ix_consultas_categoria'), table_name='consultas')
    op.drop_index(op.f('ix_consultas_area_asignada'), table_name='consultas')
    op.drop_table('consultas')
    op.drop_index(op.f('ix_usuarios_email'), table_name='usuarios')
    op.drop_table('usuarios')
    
