-- Row Level Security sem políticas. docs/DATABASE.md §5.
--
-- Nenhuma tabela guarda dado de paciente, tutor ou consulta clínica — o
-- histórico de consultas vive apenas no `hive_ce` do aparelho (TCC §4.6).
-- RLS habilitado e sem políticas para `anon`/`authenticated` bloqueia
-- qualquer acesso por essas roles: o acesso ao corpus acontece só via
-- `service_role` no back-end, que ignora RLS por definição.

alter table documento enable row level security;
alter table chunk     enable row level security;
