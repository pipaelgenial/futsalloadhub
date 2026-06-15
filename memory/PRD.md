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

## Phase 2 — Implemented (15 Fev 2026)
- Resumo Mensal Automático por atleta (carga média, sono, evolução vs. mês anterior)
- Comparação lado-a-lado de 2 atletas (métricas + ACWR sobreposto)
- Histórico de Lesões com severidade + alerta contextual
- Cálculo refinado de risco com limiares clínicos:
  - ACWR: <0.8 destreinamento, 0.8-1.3 sweet spot, 1.3-1.5 alerta, ≥1.5 alto risco
  - Monotonia: <1.0 boa variação, 1.0-1.5 ideal, 1.5-2.0 mod-alto, >2.0 crítico
  - Strain: <1500 baixo, 1500-3000 moderado, 3000-6000 elevado, >6000 extremo
- Descrição do risco em texto (sub-treinamento, risco de lesão, monotonia elevada, etc.)
- Botão "Reset Total" com confirmação textual (ELIMINAR)
- Upload de foto do jogador (JPG/PNG/WebP, máx 5MB) com endpoint público para `<img src>`

## Phase 3 — Implemented (15 Fev 2026)
- Calendário com vista 4-semanas: heatmap de carga + sessões planeadas + detalhe diário
- Endpoints `planned-sessions` (criar/listar/eliminar) e `/api/calendar?start=&days=`
- Dropdown na Vista Detalhada do Dashboard: "Equipa (Visão Geral)" por defeito + atletas individuais
- Endpoint `/api/analytics/team-detailed` (ACWR/Monotonia/Strain agregados da equipa)
- Métricas extra no Dashboard: Sono Médio + Monotonia Média (com borda colorida da zona)
- Alerta visual de Monotonia da equipa com mensagem descritiva
- Resumo Mensal com opção "Equipa (Visão Geral)" — endpoint `/api/analytics/monthly/team/overview`
- Demo seed agora também cria 5 sessões planeadas nos próximos 10 dias

## Phase 4 — Implemented (15 Fev 2026)
- **Bem-Estar Corporal (1-10)** integrado no registo de sessões com picker visual colorido (vermelho→volt)
- Bem-Estar incluído no cálculo de risco: 1-2 força "danger"; 3-4 escala risco; 5-6 modera; 7-10 saudável
- **Resumo Semanal** (substitui Resumo Mensal) com gráficos de carga + sono + bem-estar e selector 4/8/12 semanas
- **Edição inline de sessões** no perfil do atleta (data, RPE, duração, sono, bem-estar) com recálculo automático da carga
- Endpoint PUT `/api/sessions/{id}` para edição
- Novo card "Bem-Estar (7d)" no perfil + "Bem-Estar Médio" no Dashboard

## Phase 5 — Implemented (15 Fev 2026)
- **Tipo de Sessão** (TREINO/JOGO/GINÁSIO/RECUPERAÇÃO) no registo diário com picker visual
- Tipo de sessão exibido no Calendário em badges coloridos por dia + tabela de detalhe diário
- **Planeamento removido do Calendário** — apenas overview de cargas totais e tipos de sessão
- Card "Distribuição por Tipo" no Calendário com contagem por tipo nas 4 semanas
- **Vista Detalhada do Dashboard** com cores de zona em ACWR, Monotonia e Strain (verde=ideal, amarelo=alerta, vermelho=crítico) + etiqueta da zona ("Zona Ótima", "Mod-Alta", "Extremo", etc.)
- Edição inline de sessões agora também permite alterar o tipo

## Phase 6 — Deferred
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
