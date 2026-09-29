import argparse
import json
import sys
from pathlib import Path
from .runner import AGENTS, Ollama, run_agent
from .tools import Tools


def demo(name, root):
    tools = Tools(root)
    if name == 'social-editor':
        candidate={'account_id':'research-linkedin','start_second':0,'end_second':7,'caption':'Earn 15% every month. Guaranteed returns!','topic':'research','evidence_ids':['s1']}
        first=tools.review_social_draft('clip-manifest.json','social-accounts.json',json.dumps(candidate))
        context=tools.context_window('clip-manifest.json',0,7,15)
        revised=dict(candidate,end_second=22,caption='A promise of 15% every month should prompt questions. In this fictional example, the speaker explains why they would walk away.',evidence_ids=['s1','s2','s3'])
        second=tools.review_social_draft('clip-manifest.json','social-accounts.json',json.dumps(revised))
        wrong_account=dict(revised,account_id='travel-instagram')
        result={'first_draft':first,'expanded_context':context,'revised_draft':second,'different_account':tools.review_social_draft('clip-manifest.json','social-accounts.json',json.dumps(wrong_account)),
                'note':'Scripted edge-case demonstration, not an LLM run. No video was watched, cut or published.'}
    elif name == 'csv-auditor':
        result = tools.audit_csv('observations.csv',key='id',numeric_column='volume',date_column='date',as_of='2026-09-29',max_age_days=7)
    elif name == 'document-reviewer':
        result = tools.compare_documents('terms-before.md','terms-after.md')
    elif name == 'payment-reconciler':
        result = tools.reconcile_payments('invoices.csv','payments.csv','2026-09-29')
    else:
        result = tools.inspect_paper_snapshot('papers-fixture.json','agent evaluation')
    return {'mode':'deterministic_demo','agent':name,'status':'completed',
            'note':'Synthetic fixtures. No language model was called; this demonstrates the tools, not autonomous performance.', 'result':result}


def main():
    parser = argparse.ArgumentParser(description='Four useful agents with inspectable evidence. Python standard library only.')
    parser.add_argument('agent',choices=list(AGENTS)+['all'])
    parser.add_argument('--demo',action='store_true',help='Offline tool demonstration using fictional examples; no model calls')
    parser.add_argument('--workspace',type=Path,help='Only this directory can be read; defaults to examples in demo mode')
    parser.add_argument('--task',help='What the agent should investigate')
    parser.add_argument('--model',help='An installed local Ollama model supporting tools')
    parser.add_argument('--network',action='store_true',help='Allow paper-finder to send search terms to OpenAlex')
    parser.add_argument('--output',type=Path,help='Save the answer and full tool trace as JSON (outside the model)')
    args = parser.parse_args()
    if not args.demo and (not args.model or not args.task or not args.workspace or args.agent=='all'):
        parser.error('Agent mode needs one agent, --workspace, --model and --task. Or try: python -m agentkit all --demo')
    root = args.workspace or Path(__file__).resolve().parent.parent/'examples'
    try:
        if args.demo:
            result = [demo(n,root) for n in AGENTS] if args.agent=='all' else demo(args.agent,root)
        else:
            result = run_agent(args.agent,args.task,Tools(root,args.network),Ollama(args.model))
        output = json.dumps(result,indent=2,ensure_ascii=False)
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(output+'\n',encoding='utf-8')
        print(output)
        if isinstance(result,dict) and result.get('status')!='completed': return 2
    except Exception as exc:
        print('Error: '+str(exc),file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
