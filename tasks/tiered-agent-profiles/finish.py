from pathlib import Path
p=Path('ai/tests/test_sync_mcps.py'); s=p.read_text(); at=s.index('    def test_disabled_claude_servers_are_not_imported')
s=s[:at]+'''    def test_provider_specific_configuration(self):
        self.base.metadata['codexConfig'] = {'model_reasoning_effort': 'high'}
        self.base.metadata['claudeConfig'] = {'effort': 'low'}
        self.run_sync()
        self.assertEqual(self.profile('codex')['codexConfig']['model_reasoning_effort'], 'high')
        self.assertNotIn('claudeConfig', self.profile('codex').metadata)
        self.assertEqual(self.profile('claude')['claudeConfig']['effort'], 'low')
        self.assertNotIn('codexConfig', self.profile('claude').metadata)

    def test_prune_only_managed_and_check_is_non_destructive(self):
        self.run_sync()
        old = self.store / 'ai_stack_codex_old.md'
        custom = self.store / 'ai_stack_codex_custom.md'
        other = self.store / 'another_codex_old.md'
        old.write_text(sync.MARKER)
        custom.write_text('user owned')
        other.write_text(sync.MARKER)
        self.assertTrue(self.run_sync(check=True, prune=True)['changed'])
        self.assertTrue(old.exists())
        self.assertTrue(self.run_sync(prune=True)['changed'])
        self.assertFalse(old.exists())
        self.assertTrue(custom.exists())
        self.assertTrue(other.exists())
        self.assertFalse(self.run_sync(prune=True)['changed'])

    def test_base_dir_precedes_local_and_builtin(self):
        # Use the real lookup instead of the fixture's mocked base profile.
        with patch.object(sync, 'base_profile', sync_original_base_profile):
            base_dir = self.home / 'bases'
            base_dir.mkdir()
            self.store.mkdir(parents=True)
            (self.store / 'developer.md').write_text('---\\ndescription: local\\n---\\nlocal')
            preferred = base_dir / 'developer.md'
            preferred.write_text('---\\ndescription: preferred\\n---\\npreferred')
            self.assertEqual(sync.base_profile(self.home, 'developer', base_dir)['description'], 'preferred')
            preferred.unlink()
            self.assertEqual(sync.base_profile(self.home, 'developer', base_dir)['description'], 'local')
            (self.store / 'developer.md').unlink()
            self.assertTrue(sync.base_profile(self.home, 'developer', base_dir)['description'])

'''+s[at:]; s=s.replace('SPEC.loader.exec_module(sync)\n','SPEC.loader.exec_module(sync)\nsync_original_base_profile = sync.base_profile\n'); p.write_text(s)
p=Path('ai/vars.example.yml'); s=p.read_text().replace('cao_mcp_profiles: [code_supervisor, developer, reviewer]', '''cao_mcp_profiles: [code_supervisor, developer_low, developer_medium, developer_high, reviewer_basic, reviewer_advanced]
# Defina o dicionário completo ao substituir os níveis de esforço.
cao_profile_efforts:
  code_supervisor: {codex: medium, claude: medium}
  developer_low: {codex: low, claude: low}
  developer_medium: {codex: medium, claude: medium}
  developer_high: {codex: high, claude: high}
  reviewer_basic: {codex: low, claude: low}
  reviewer_advanced: {codex: high, claude: high}'''); p.write_text(s)
p=Path('ai/README.md'); s=p.read_text(); a=s.index('Os arquivos dos clientes são apenas lidos.'); b=s.index('Use esses perfis para compartilhar',a); s=s[:a]+'''Os arquivos dos clientes são apenas lidos. Os perfis base ficam em
`~/.local/share/ai-stack/profiles/`, e as versões por provedor são geradas no
agent store. Execute `ansible-playbook ai/mcp.yml -K` para instalar os perfis e
sincronizá-los. Os nomes abaixo recebem o prefixo `ai_stack_codex_` ou
`ai_stack_claude_` conforme o provedor:

| Perfil | Finalidade | Esforço padrão |
| --- | --- | --- |
| `code_supervisor` | Coordena tarefas e revisões | medium |
| `developer_low` | Alterações simples e mecânicas | low |
| `developer_medium` | Funcionalidades e correções com testes | medium |
| `developer_high` | Arquitetura, riscos elevados ou investigação complexa | high |
| `reviewer_basic` | Revisão de tarefas baixas e médias | low |
| `reviewer_advanced` | Revisão de tarefas altas ou com riscos de segurança, produção ou perda de dados | high |

O supervisor registra o nível e a justificativa no arquivo da tarefa, considera
ambiguidades, quantidade de arquivos e riscos, e escolhe o worker do mesmo provedor.
`[level: low|medium|high]` ou `[nivel: baixo|medio|alto]` substitui a classificação.
Após duas rejeições da mesma tarefa, o desenvolvedor sobe um nível. Perfis antigos
marcados como gerenciados e fora da lista são removidos durante o playbook;
arquivos sem a marca são preservados.

Altere `cao_profile_efforts` no inventário ou em um arquivo de variáveis, seguindo
o exemplo completo em `ai/vars.example.yml`, e execute novamente o playbook.
Cada perfil aceita `codex` (minimal, low, medium, high, xhigh) e `claude` (low,
medium, high, xhigh); os valores são validados antes da instalação.

'''+s[b:]; s=s.replace('| `cao_mcp_profiles` | `[code_supervisor, developer, reviewer]` | Perfis base locais ou do pacote CAO |','| `cao_mcp_profiles` | Seis perfis da tabela acima | Perfis base a sincronizar |\n| `cao_profile_efforts` | Níveis da tabela acima | Esforço por perfil e provedor |'); p.write_text(s)
