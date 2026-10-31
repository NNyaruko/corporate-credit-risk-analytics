/**
 * Editable portfolio review deck, built from the checked analytics outputs.
 * Requires @oai/artifact-tool in an authoring environment. The delivered PPTX
 * itself has no JavaScript dependency. Run from a temporary build folder with
 * this file and a node_modules link, passing the repository root as argv[2].
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {Presentation, PresentationFile} from '@oai/artifact-tool';

const root = path.resolve(process.argv[2] || '.');
const out = path.join(root, 'outputs');
const scratch = path.resolve(process.env.SLIDE_BUILD_DIR || path.join(root, '.slide-build'));
await fs.mkdir(scratch,{recursive:true});
const metrics = JSON.parse(await fs.readFile(path.join(out,'metrics.json'),'utf8'));
function csvRows(raw){
 const rows=[];let row=[],field='',quoted=false;
 for(let i=0;i<raw.length;i++){const c=raw[i];if(c==='"'){if(quoted&&raw[i+1]==='"'){field+='"';i++;}else quoted=!quoted;}else if(c===','&&!quoted){row.push(field);field='';}else if(c==='\n'&&!quoted){row.push(field.replace(/\r$/,''));rows.push(row);row=[];field='';}else field+=c;}
 if(field||row.length){row.push(field);rows.push(row);}const headers=rows.shift();return rows.filter(r=>r.length===headers.length).map(r=>Object.fromEntries(headers.map((h,i)=>[h,r[i]])));
}
const calibration=csvRows(await fs.readFile(path.join(out,'calibration_bins.csv'),'utf8')).filter(r=>r.model==='Logistic');
const support=csvRows(await fs.readFile(path.join(out,'scenario_support.csv'),'utf8'));
const baseGdpOutside=Number(support.find(r=>r.scenario==='Base'&&r.feature==='gdp_growth_pct').outside_training_range_n);
const logistic=metrics.test_metrics.find(r=>r.model==='Logistic');
const tree=metrics.test_metrics.find(r=>r.model==='Decision tree');
const periods={train:'2017 to 2019',embargo:'2020 and 2022',validation:'2021',test:'2023 to 2024'};
const names={train:'Training',embargo:'Maturity embargo',validation:'Validation',test:'Test'};
const data={total:metrics.n_model_rows,splits:metrics.split_summary.map(r=>({name:names[r.split],period:periods[r.split],n:r.n})),logistic:{...logistic,brier:logistic.brier_score},tree:{...tree,brier:tree.brier_score},test_n:logistic.n,default_rate:logistic.default_rate,mean_pd:logistic.mean_pd,calibration:calibration.map((r,i)=>({label:String(i+1),predicted:Number(r.mean_pd),observed:Number(r.observed_default_rate)})),scenarios:metrics.scenarios.map(r=>({label:r.scenario,loss:r.ecl_proxy_cny_m,pd:r.mean_pd}))};
const C={navy:'#142B40',teal:'#087F8C',gray:'#536575',paper:'#FAFAF7',light:'#E8EEEF',ink:'#172B3A',coral:'#BF744B'};
const FONT='DejaVu Sans';
const deck=Presentation.create({slideSize:{width:1280,height:720}});
function text(slide,s,x,y,w,h,size=25,color=C.ink,bold=false){
 const sh=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{style:'solid',fill:'none',width:0}});
 sh.text=s;sh.text.style={typeface:FONT,fontSize:size,color,bold,verticalAlignment:'top',insets:0,autoFit:'none'};return sh;
}
function slide(title,number,notes){
 const s=deck.slides.add();s.background.fill=C.paper;
 text(s,title,64,46,1152,100,44,C.navy,true);
 text(s,'Independent portfolio demonstration using synthetic data',64,667,1080,28,16,C.gray);
 text(s,String(number).padStart(2,'0'),1160,667,56,28,16,C.gray);
 s.speakerNotes.text=notes;return s;
}
function table(s,values,x,y,width,height,widths){
 const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width,height,columnWidths:widths,values});
 t.borders.assign({style:'solid',fill:'#CDD6DA',width:1});
 for(let r=0;r<values.length;r++)for(let c=0;c<values[0].length;c++){
  const cell=t.getCell(r,c);cell.fill=r===0?C.navy:(r%2? '#FFFFFF':C.light);
  cell.text.style={typeface:FONT,fontSize:23,color:r===0?'#FFFFFF':C.ink,bold:r===0,alignment:c===0?'left':'center',verticalAlignment:'middle',insets:12};
 }
 return t;
}
const pct=(x,d=1)=>(100*x).toFixed(d)+'%';
const num=(x,d=0)=>Number(x).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const s1=slide('Corporate credit risk model review',1,'Source: outputs/metrics.json and data/processed/model_data.csv. All borrowers, statements, repayments and macro observations are synthetic. Each borrower appears once. Outcomes describe the next 12 months and are fully observed.');
text(s1,num(data.total),64,167,410,86,72,C.teal,true);
text(s1,'usable synthetic borrower records',64,254,560,48,25,C.gray);
text(s1,'12 months',700,167,450,86,62,C.navy,true);
text(s1,'forward default outcome',700,254,490,48,25,C.gray);
table(s1,[['Sample','Snapshot period','Borrowers'],...data.splits.map(r=>[r.name,r.period,num(r.n)])],64,320,1152,245,[360,480,312]);
text(s1,'Embargo years allow labels to mature before model selection. All test outcomes mature by the end of 2025.',64,585,1152,64,24,C.ink);

const s2=slide('Held out model performance',2,'Source: outputs/model_metrics.csv. Models train on the training cohort only. Validation chooses tree parameters and F1 thresholds. The test cohort remains frozen. ROC-AUC and average precision are rank metrics. Brier score evaluates probability error.');
table(s2,[['Metric','Logistic regression','Decision tree'],['ROC-AUC',data.logistic.roc_auc.toFixed(3),data.tree.roc_auc.toFixed(3)],['Average precision',data.logistic.average_precision.toFixed(3),data.tree.average_precision.toFixed(3)],['Brier score',data.logistic.brier.toFixed(3),data.tree.brier.toFixed(3)],['Recall at locked threshold',pct(data.logistic.recall),pct(data.tree.recall)]],64,173,1152,300,[580,286,286]);
text(s2,`Test sample: ${num(data.test_n)} borrowers, ${pct(data.default_rate)} observed default rate.`,64,510,1152,46,26,C.navy,true);
text(s2,`Validation F1 selects thresholds of ${data.logistic.threshold.toFixed(2)} for logistic regression and ${data.tree.threshold.toFixed(2)} for the tree.`,64,570,1152,66,25,C.gray);

const s3=slide('Probability calibration by risk group',3,'Source: outputs/calibration_bins.csv (logistic regression, test cohort). Eight quantile bins use the frozen logistic test scores. Points summarize mean predicted probability and observed default frequency. Descriptive bin comparisons do not constitute an independent recalibration.');
const chart1=s3.charts.add('line',{position:{left:64,top:164,width:770,height:430},categories:data.calibration.map(r=>r.label),lineOptions:{smooth:false},series:[{name:'Predicted PD',values:data.calibration.map(r=>Number(r.predicted.toFixed(8))),line:{style:'solid',fill:C.teal,width:3},marker:{symbol:'circle',size:7,fill:C.teal}},{name:'Observed default',values:data.calibration.map(r=>Number(r.observed.toFixed(8))),line:{style:'solid',fill:C.coral,width:3},marker:{symbol:'square',size:7,fill:C.coral}}],hasLegend:true,legend:{position:'bottom',textStyle:{typeface:FONT,fontSize:21}},xAxis:{title:{text:'Test score groups from lower to higher risk',textStyle:{typeface:FONT,fontSize:20}},textStyle:{typeface:FONT,fontSize:18}},yAxis:{min:0,numberFormatCode:'0%',textStyle:{typeface:FONT,fontSize:20},majorGridlines:{style:'solid',fill:'#DCE3E6',width:1}},chartFill:C.paper,plotAreaFill:C.paper});
text(s3,pct(data.mean_pd),884,180,332,70,54,C.teal,true);
text(s3,'mean predicted PD',884,256,332,70,25,C.gray);
text(s3,pct(data.default_rate),884,359,332,70,54,C.navy,true);
text(s3,'observed default rate',884,435,332,70,25,C.gray);
text(s3,'Calibration matters when probabilities feed expected loss calculations.',64,606,1152,40,25,C.ink);

const s4=slide('Conditional stress loss proxy',4,'Source: outputs/scenario_summary.csv. Same frozen test borrowers and coefficients in every case. EAD proxy is debt in CNY millions. LGD is an illustrative fixed 45%. Proxy loss is sum(debt × PD × LGD). Shocks are illustrative feature perturbations, not regulatory or causal stress forecasts.');
const chart2=s4.charts.add('bar',{position:{left:64,top:163,width:690,height:410},categories:data.scenarios.map(r=>r.label),series:[{name:'12 month loss proxy',values:data.scenarios.map(r=>Number(r.loss.toFixed(4))),fill:C.teal}],hasLegend:false,barOptions:{direction:'column',grouping:'clustered',gapWidth:125},dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'#,##0',textStyle:{typeface:FONT,fontSize:22,color:C.navy,bold:true}},xAxis:{textStyle:{typeface:FONT,fontSize:22}},yAxis:{min:0,title:{text:'CNY million',textStyle:{typeface:FONT,fontSize:20}},numberFormatCode:'#,##0',textStyle:{typeface:FONT,fontSize:18},majorGridlines:{style:'solid',fill:'#DCE3E6',width:1}},chartFill:C.paper,plotAreaFill:C.paper});
text(s4,'Severe assumptions',800,179,416,42,29,C.navy,true);
text(s4,'Leverage rises by 0.10\nDSCR falls by 30%\nBorrowing rate rises by 2 pp\nGDP growth falls by 4 pp',800,244,416,235,25,C.ink);
text(s4,'12 month loss = debt × PD × 45% LGD\nIllustrative shocks on the fixed test cohort',800,482,416,91,22,C.gray);
text(s4,`Mean PD: ${pct(data.scenarios[0].pd)} base, ${pct(data.scenarios[2].pd)} severe.`,64,596,1152,40,26,C.navy,true);

const s5=slide('Review conclusions and limitations',5,'Sources: outputs/metrics.json, outputs/coefficients.csv, outputs/scenario_support.csv and repository methodology documentation. GDP growth falls outside the training feature range for 800 of 1598 base borrowers and all adverse and severe observations. This independent synthetic portfolio is a software demonstration. It does not represent any employer model, customer dataset, lending decision, regulatory calculation or deployment.');
text(s5,'Model evidence',64,174,500,46,31,C.teal,true);
text(s5,'Temporal separation prevents using future outcomes in training. Validation selects operating thresholds before test evaluation.',64,242,510,138,27,C.ink);
text(s5,'HC1 standard errors quantify coefficient uncertainty. Separate VIF diagnostics assess collinearity.',64,422,510,132,27,C.ink);
text(s5,'Limits of interpretation',700,174,516,46,31,C.navy,true);
text(s5,'Synthetic generation constrains what these results establish. Shared macro conditions can affect the independence assumed by HC1 inference.',700,242,516,138,27,C.ink);
text(s5,`GDP growth is outside the training range for ${num(baseGdpOutside)} of ${num(data.test_n)} base borrowers and all stressed borrowers. Scenario results rely on extrapolation.`,700,422,516,160,27,C.ink);

for (const [i,s] of deck.slides.items.entries()){
 const blob=await deck.export({slide:s,format:'png',scale:1});
 await fs.writeFile(path.join(scratch,`slide-${i+1}.png`),new Uint8Array(await blob.arrayBuffer()));
}
await fs.copyFile(path.join(scratch,'slide-2.png'),path.join(out,'charts','slides_preview.png'));
// PNG previews are the visual QA surface. PDF conversion can use LibreOffice
// after export when the author's PDF renderer lacks a standard-font bundle.
const candidate=path.join(scratch,'candidate.pptx');
await (await PresentationFile.exportPptx(deck)).save(candidate);
const skill=process.env.PRESENTATIONS_SKILL_ROOT || '/root/.codex/skills/builtins/presentations';
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
await fs.mkdir(path.join(scratch,'final'),{recursive:true});
const finalPath=path.join(scratch,'final','validated-'+Date.now()+'.pptx');
await finalizePresentation({workspaceDir:path.dirname(root),candidatePath:candidate,finalPath,pythonExecutable:process.env.CODEX_PRIMARY_RUNTIME_PYTHON,integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','1','--require-native-table-slide','2'],explicitTotalSlideCount:5,requiredNativeTableOwnerSlides:[1,2],requiredNativeChartOwnerSlides:[3,4],materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,receiptPath:path.join(scratch,'validation-'+Date.now()+'.json')});
await fs.copyFile(finalPath,path.join(out,'Credit_Risk_Review.pptx'));
console.log('Created 5 editable slides with native tables and charts.');
