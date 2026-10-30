import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const root=path.resolve(import.meta.dir,'..');
const require=createRequire(path.join(root,'x-publisher/package.json'));
const frontmatter=require('front-matter');
const yaml=require('js-yaml');
test('skill metadata and maintained workflow links resolve without reading credential or vault files',()=>{
 const skill=frontmatter(fs.readFileSync(path.join(root,'SKILL.md'),'utf8'));
 assert.equal(skill.attributes.name,'jdy_writer');assert.ok(skill.attributes.description);
 for(const name of ['SKILL.md','README.md','references/workflow-x.md','references/workflow-wechat.md','references/workflow-draft.md','references/workflow-publication.md']){
  const body=fs.readFileSync(path.join(root,name),'utf8').replace(/```[\s\S]*?```/g,'').replace(/`[^`]*`/g,'');
  for(const match of body.matchAll(/\]\(([^)]+)\)/g)){
   const target=match[1].split('#')[0];if(!target||target.includes('://'))continue;
   assert.ok(fs.existsSync(path.resolve(root,path.dirname(name),target)),`${name}: unresolved reference ${target}`);
  }
 }
});
test('PR workflow runs offline checks with pinned actions and read-only repository permission',()=>{
 const file=path.resolve(root,'../.github/workflows/jdy-writer.yml');
 const workflow=yaml.safeLoad(fs.readFileSync(file,'utf8'));
 assert.equal(workflow.permissions.contents,'read');assert.ok(workflow.on.pull_request);
 for(const step of workflow.jobs.test.steps){if(step.uses)assert.match(step.uses,/@[a-f0-9]{40}$/);}
 const checkout=workflow.jobs.test.steps.find((s:any)=>s.uses?.startsWith('actions/checkout@'));
 assert.equal(checkout.with['persist-credentials'],false);
});
