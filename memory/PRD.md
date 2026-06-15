# Futsal Load Hub - PRD

## Original Problem Statement
Aplicação para monitorizar as cargas dos atletas de uma equipa de futsal.
Capacidades core: registar atletas, registar cargas diárias (RPE × duração),
qualidade do sono, calcular ACWR, monotonia, strain e alertas de risco de lesão.
Tema escuro desportivo com cores de destaque vibrantes, visualizações limpas
e estilo dashboard.

## User Personas
- **Treinador de Futsal** (utilizador único): Configura equipa, gere plantel,
  regista sessões diárias, monitoriza risco de lesão.

## Core Requirements (static)
- Registo/login de treinador (JWT)
- Perfil de equipa: nome, escalão, época
- CRUD de atletas (nome, posição, número)
- Registo de sessões: RPE 1-10, duração, qualidade do sono 1-5, data
- Cálculo: load = RPE × duração, carga aguda (7d), carga crónica (avg 4 semanas),
  ACWR = aguda/crónica, monotonia, strain
- Regra "Dados Insuficientes": ACWR só exibido após 28 dias do primeiro treino
- Regra "Insira dados da equipa": empty state no perfil
- Alertas de risco: safe (0.8-1.3), warning (<0.8 ou 1.3-1.5), danger (>1.5)
- Dashboard com carga aguda e carga crónica visíveis

## Phase 1 — Implemented (15 Fev 2026)
- JWT auth (register, login, logout) com seed admin treinador@futsal.pt/treinador123
- Perfil de Equipa (CRUD com empty state "Insira dados da equipa")
- Gestão de Atletas (criar/listar/eliminar)
- Registo de Sessões (RPE × duração + sono + carga calculada em live)
- Dashboard: métricas agregadas (atletas, carga aguda média, crónica média),
  alertas de risco, gráfico ACWR 60 dias com banda segura, tabela de visão geral
- Detalhe de Atleta com gráfico 60 dias, métricas individuais, histórico de sessões
- Mensagem "DADOS INSUFICIENTES" no painel ACWR antes dos 28 dias
- Seed de demo (1 equipa + 8 atletas + ~225 sessões em 45 dias)

## Phase 2 — Deferred (Backlog priorizado)
### P0
- **Resumo Mensal Automático**: para cada atleta, média de carga e qualidade do sono
  por mês, com destaque de evolução (delta vs. mês anterior)
- **Comparação entre 2 atletas**: vista lado-a-lado de métricas e gráficos ACWR

### P1
- Exportação CSV/PDF dos resumos mensais
- Filtros por período (semana, mês) no dashboard
- Notificações in-app para alertas de risco elevado

### P2
- Multi-treinador (treinador principal + adjuntos com permissões)
- Histórico de lesões associado por atleta
- Importação em massa de sessões via CSV

## Architecture
- Backend: FastAPI + Motor (async MongoDB), JWT (PyJWT) + bcrypt
- Frontend: React 19 + react-router-dom 7 + axios + recharts + sonner + lucide-react
- Auth: httpOnly cookie + Bearer token fallback (localStorage `fld_token`)
- Tema: Performance Pro dark (#0A0A0A) + accent volt yellow (#CCFF00),
  Barlow Condensed (headers) + Manrope (body) + JetBrains Mono (números)

## Next Actions
1. Implementar resumo mensal por atleta
2. Implementar página de comparação de 2 atletas
3. Refatorar server.py em módulos (routers/services)
