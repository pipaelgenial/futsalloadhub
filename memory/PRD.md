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

## Phase 6 — Implemented (16 Fev 2026)
- **Tipografia responsiva**: H1 reduzido para `text-3xl sm:text-4xl md:text-5xl` e métricas para `text-2xl sm:text-3xl md:text-4xl` para boa legibilidade em mobile/tablet/desktop
- **Dashboard reorganizado**: removidos os 7 cards de métricas do topo; Vista Detalhada da Equipa aparece em primeiro lugar; alertas e tabela depois
- **Visão Geral da Equipa coloreada**: ACWR/Monotonia/Strain pintados conforme zona (verde/amarelo/vermelho)
- **Calendário mensal**: dropdown para escolher mês + selector de span (1/2/3/6 meses); dias fora do mês ficam atenuados; navegação `< / >` agora salta de mês em mês
- **Descritivos no Registo Diário**:
  - PSE (RPE) 1-10 com botões coloridos e texto descritivo por valor (Muito Leve → Esforço Máximo)
  - Qualidade do Sono 1-5 com descritivo (Muito Mau → Excelente)
  - Bem-Estar 1-10 com descritivo por valor (Esgotamento profundo → Energia radiante)
- Todos os pickers atualizam o texto descritivo em tempo real

## Phase 7 — Multi-Team + Calendar Redesign + Copy Last Session (17 Jun 2026)
- **Multi-Equipa (até 5)**: backend (GET/POST/PUT/DELETE /api/teams, POST /api/teams/{id}/activate),
  filtros por active_team_id em todas as queries, cascade delete, upload de logo
- **TeamSwitcher**: dropdown no sidebar e mobile com logo + nome da equipa ativa,
  troca via POST /api/teams/{id}/activate + window.location.reload, atalho 'Gerir equipas'
- **TeamProfile reescrito**: gere até 5 equipas, criação/edição/eliminação inline + upload de logo
- **Calendar redesenhado**:
  - Fundo da célula colorido pelo tipo de sessão dominante (Treino/Jogo/Ginásio/Recuperação)
  - Intensidade do fundo escalada pela carga (loadIntensity)
  - Cor do número da carga por zona de volume (cinza<800, lime<2500, amarelo<4500, laranja<7000, vermelho)
  - Modo "Mês" (default) e modo "Intervalo personalizado" com date pickers + presets 7D/30D/90D
- **Copiar Último Treino**: botão em LogSession.jsx que faz GET /api/sessions?athlete_id=X
  e preenche o formulário com a última sessão (session_type, rpe, duração, sono, bem-estar).
  Toast informativo quando não há histórico.
- **Seed idempotente**: POST /api/seed/demo agora repõe active_team_id para a equipa seed recriada

## Phase 8 — Notificações + Calendário per-athlete + Refinements (17 Jun 2026)
- **Notificações in-app**: GET /api/alerts calcula on-the-fly (ACWR alto/baixo, monotonia crítica, strain extremo, sono ≤2, bem-estar ≤3, lesões abertas)
- **NotificationsBell** no sidebar e mobile bar com badge não-vistos, dropdown com listagem, marcação 'vista' (ao abrir) e 'resolvida' (manual), reabrir, limpar histórico. Toast automático no Dashboard para alertas danger novos (throttle 5min). Estado persistido em localStorage.
- **Calendar limiares per-athlete**: `loadTextColor(load, athletes_count)` e `loadIntensity(load, athletes_count)` usam carga média por atleta para evitar cores falsas. Limiares: <300 cinza, 300-600 lime, 600-900 amarelo, 900-1200 laranja, >1200 vermelho.
- **Calendar modo único**: remoção do modo "Intervalo personalizado" e date pickers. Só fica modo Mês com span 1/2/3 meses.
- **TeamSwitcher dinâmico**: refetch de `/api/teams` ao mudar de rota E ao abrir o dropdown — equipas novas/eliminadas refletem sem reload.
- **TeamProfile sem botão ATIVAR**: trocar equipa é exclusivamente via o switcher na sidebar (UX unificada).

## Phase 9 — Configurable Load Thresholds (17 Jun 2026)
- **Limiares de carga por equipa**: novo campo `load_thresholds = {ideal, moderate, high, very_high}` (UA/atleta/dia) com defaults 300/600/900/1200. Persistido em MongoDB.
- **Backend**: POST/PUT /api/teams aceitam `load_thresholds`; validação no `_sanitize_thresholds` (positivos e estritamente crescentes); GET /api/team e /api/teams aplicam defaults quando ausentes.
- **Frontend TeamProfile**: form de edição com 4 inputs coloridos + 5 presets por escalão (Sub-13: 200/400/600/800, Sub-15: 250/500/750/1000, Sub-17: 300/600/900/1200, Sub-19: 350/700/1050/1400, Sénior: 400/800/1200/1600) + botão "Repor 300/600/900/1200". Validação local impede save com limiares não-crescentes.
- **Calendar**: busca os limiares da equipa ativa via GET /api/team. `loadTextColor` e `loadIntensity` recebem `th` como parâmetro. Legenda atualiza dinamicamente com os limiares configurados.

## Phase 10 — Roles, Admin Panel & Athlete Invites (17 Jun 2026)
- **Sistema de papéis**: admin, coach, player. Enforcement por path no `get_current_user`: player só /api/auth|player|invite; admin só /api/auth|admin; coach o resto.
- **Admin bootstrap**: `pedrompsantos84@gmail.com / amarense` criado/forçado a admin+active em cada arranque.
- **Registo de coaches em pending**: POST /api/auth/register não devolve token; login bloqueia status=pending/suspended com 403.
- **Admin Panel** (`/admin`): listagem com stats (equipas/atletas/sessões/último login), filtros TODOS/PENDENTE/ATIVO/SUSPENSO + pesquisa, ações validar/suspender/reativar/eliminar, cascade delete completo, admin auto-protegido.
- **Convite de atleta**:
  - POST `/api/athletes/{id}/invite` cria/refresha token único
  - Modal automática ao criar atleta + botão "Convite de acesso" em cada card (página `/atletas`)
  - Página pública `/convite/{token}` permite o atleta definir email/password
  - Atleta apagado → conta player + invites apagados (cascade)
- **Vista de Atleta** (`/atleta`, `/atleta/registar`, `/atleta/historico`):
  - PlayerShell minimal sem sidebar
  - Acesso restrito a `/api/player/*` (próprias sessões, sem campo `load`)
  - 403 ao tentar tocar em endpoints de coach
  - PlayerHome com stats + última sessão + 2 CTAs
  - PlayerLogSession (RPE, duração, tipo, sono, bem-estar, notas)
  - PlayerSessions (histórico NEWEST-FIRST sem coluna de carga)

## Phase 11 — Admin Per-Coach Team Limit + Demo Risk + Locked Player History (18 Jun 2026)
- **Limite de equipas por coach configurável pelo admin**: novo campo `max_teams` (1..5, default 5) por utilizador. Endpoint `POST /api/admin/users/{id}/max-teams`. UI no AdminPanel mostra "1 2 3 4 5" com botão atual destacado e botões "tooLow" (abaixo do nº de equipas atuais) bloqueados.
- **POST /api/teams** valida agora contra `user.max_teams` (com cap absoluto MAX_TEAMS_PER_USER=5).
- **Demo seed com risco**: 3 atletas (índices 0, 2, 5) recebem injeção de carga aguda nos últimos 7 dias (RPE 9-10, duração 100-120min, sono 1-2, bem-estar 2-4) → produz ACWR HIGH, sleep_poor, wellness_low e potenciais strain_extreme alerts.
- **Atleta NÃO apaga sessões**: removido endpoint `DELETE /api/player/sessions/{id}` e o botão de eliminar no `PlayerSessions.jsx`. Mensagem no histórico: "Para alterar ou eliminar, contacta a equipa técnica."
- **Coach edita sessões**: já existente em `AthleteDetail.jsx` (PUT /api/sessions/{id}).

## Phase 12 — Password Recovery via Email (Resend) (18 Jun 2026)
- **Integração Resend** (sandbox `onboarding@resend.dev`): novo SDK `resend>=2.0.0` em requirements.txt. RESEND_API_KEY + SENDER_EMAIL em backend/.env.
- **Endpoints públicos**:
  - `POST /api/auth/forgot` — gera token URL-safe (32 chars), TTL 1h, invalida tokens anteriores do user, envia email com link via Resend (assíncrono via `asyncio.to_thread`). Resposta SEMPRE 200 para evitar enumeração de emails.
  - `GET /api/auth/reset/{token}` — valida token (404 inválido, 410 expirado).
  - `POST /api/auth/reset/{token}` — body `{password: min 6}`, atualiza hash + apaga token (one-time use) + invalida outros tokens pendentes.
- **Email HTML** com branding FUTSAL LOAD HUB, botão CTA lime, link copy-paste, aviso de 60min de validade.
- **Frontend**:
  - `/recuperar-password` (ForgotPassword.jsx): form simples + ecrã "Pedido enviado" com lembrete de SPAM.
  - `/recuperar-password/:token` (ResetPassword.jsx): valida token, form de nova password + confirmação, ecrã "Password atualizada" + redirect login.
  - Link "Esqueceste a password?" adicionado em Login.jsx abaixo do botão ENTRAR.
- **Limitação sandbox**: o domínio `onboarding@resend.dev` só envia para o email registado na conta Resend; em produção é necessário verificar domínio próprio em https://resend.com/domains.

## Phase 13 — Code Review Fixes (18 Jun 2026)
- **Array-index-as-key** corrigido em 3 ficheiros (Cell key passou a usar `m.week`/`m.month`/`row[0].iso` em vez de índice):
  - WeeklySummary.jsx (linha 140)
  - MonthlySummary.jsx (linha 146)
  - Calendar.jsx (linha 122)
- **`is` literal comparisons**: verificado com `ruff F632` → ZERO ocorrências (falso positivo no relatório do code review)
- **Hook deps**: ESLint exhaustive-deps não devolveu blockers nos ficheiros listados. Os useEffects atuais usam closures intencionais (`load()` lê estado atual) — adicionar deps levaria a loops infinitos. Sem alterações.

### Deferred com justificação
- **Refactor `compute_metrics_for_athlete` (214 linhas / cyclomatic 59)**: função pura, testada via pytest, todos os ramos cobrem zonas de risco específicas (ACWR/monotonia/strain/wellness). Refactor traria risco de regressão num ficheiro com 24+ testes a passar. Marcado para fase futura quando refactorizar `server.py` em routers/services.
- **`random` no seed**: intencional — `random.seed(42)` garante demo data reprodutível. `secrets` quebraria a reprodutibilidade (e o seed não é security-sensitive, apenas gera UA/RPE/duração de treino).
- **Hardcoded creds em tests**: são as credenciais documentadas em `/app/memory/test_credentials.md`. Os ficheiros de teste estão em `.gitignore`-able directory e existem para o testing agent.
- **localStorage tokens**: já usamos `httpOnly cookies` (`set_auth_cookie` com httponly=True, secure=True, samesite=none) — o token em localStorage é fallback para o header `Authorization: Bearer` em CORS cross-origin.
- **Type hints, ternários, complex AdminPanel/NotificationsBell**: cosméticos sem impacto funcional. Marcados como future polish.

## Phase 14 — Deferred
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
2. Implementar página de comparação de 2 atletas (parcialmente já existe via /comparar)
3. Refatorar server.py em módulos (routers/services)
4. Tornar todo o seed/demo idempotente (atualmente só o active_team_id é refeito; sessões/atletas/injuries são recriados sempre)
