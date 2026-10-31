/** Authoring source for the delivered workbook.
 * Requires the OpenAI artifact-tool authoring runtime; it is NOT needed to open
 * or use Credit_Risk_Review.xlsx. Run from a temporary directory with the runtime
 * node_modules symlink and pass the repository path as the first argument.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const repo = path.resolve(process.argv[2] || process.cwd());
const outputDir = path.resolve(process.argv[3] || path.join(repo, 'outputs', 'excel-build'));
await fs.mkdir(outputDir, {recursive:true});
function csv(text) {
  const rows=[]; let row=[], field='', quoted=false;
  for(let i=0;i<text.length;i++) {const c=text[i];
    if(c==='"') {if(quoted&&text[i+1]==='"'){field+='"';i++;}else quoted=!quoted;}
    else if(c===','&&!quoted){row.push(field);field='';}
    else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(field);if(row.some(Boolean))rows.push(row);row=[];field='';}
    else field+=c;
  }
  if(field||row.length){row.push(field);rows.push(row);}
  const headers=rows.shift();return rows.map(r=>Object.fromEntries(headers.map((h,i)=>[h,r[i]])));
}
const readCSV=async f=>csv(await fs.readFile(path.join(repo,f),'utf8'));
const data=await readCSV('outputs/test_predictions.csv');
const coef=await readCSV('outputs/coefficients.csv');
const coefficients=Object.fromEntries(coef.map(r=>[r.term,Number(r.coefficient)]));
const metricRows=await readCSV('outputs/model_metrics.csv');
const n=data.length, first=7,last=first+n-1;
const predictors=['leverage','dscr','interest_rate_pct','gdp_growth_pct','past_due_30d'];
const beta=[coefficients.const??coefficients.Intercept??coefficients.intercept,...predictors.map(k=>coefficients[k])];
if(beta.some(v=>!Number.isFinite(v)))throw new Error('Missing logistic coefficients');
if(n<1||data.some(r=>!Number.isFinite(Number(r.pd_logistic))))throw new Error('Missing test predictions');
const wb=Workbook.create();
const summary=wb.worksheets.add('Summary'), assumptions=wb.worksheets.add('Assumptions'), scoring=wb.worksheets.add('Scoring'), source=wb.worksheets.add('Source'), checks=wb.worksheets.add('Checks');
const colors={navy:'#16324A',teal:'#0A7A78',light:'#EDF4F7',gray:'#667582',blue:'#2056B3',green:'#187340',amber:'#FFF2CD',red:'#A33131'};
function standard(s, range) {s.showGridLines=false;s.getRange(range).format.font={name:'Arial',size:10,color:'#1B2B3A'};s.getRange(range).format.rowHeight=22;s.getRange(range).format.verticalAlignment='center';}
function title(s,text,end='K'){s.getRange(`C2:${end}2`).format.rowHeight=30;s.getRange('C2').values=[[text]];s.getRange('C2').format.font={size:16,bold:true,color:colors.navy};s.getRange(`C3:${end}3`).format.borders={bottom:{style:'thin',color:colors.teal}};}
function header(s,range){s.getRange(range).format={fill:colors.navy,font:{bold:true,color:'#FFFFFF'},rowHeight:30,wrapText:true,horizontalAlignment:'center',verticalAlignment:'center'};}
function sourceLink(s,r){s.getRange(r).format.font.color=colors.green;}
function input(s,r){s.getRange(r).format.fill=colors.amber;s.getRange(r).format.font.color=colors.blue;}
function fmt(s,r,v){s.getRange(r).setNumberFormat(v);}
const money='#,##0.0;(#,##0.0);–',pct='0.0%;(0.0%);–',ratio='0.00"x"';
for(const s of [summary,assumptions,checks]){standard(s,'A1:K48');s.getRange('A1:B48').format.columnWidth=2.5;s.getRange('C1:C48').format.columnWidth=29;s.getRange('D1:F48').format.columnWidth=14;s.getRange('G1:G48').format.columnWidth=3;s.getRange('H1:H48').format.columnWidth=23;s.getRange('I1:K48').format.columnWidth=12;}
summary.tabColor=colors.navy;assumptions.tabColor=colors.teal;
title(summary,'Corporate credit risk review');
summary.getRange('C3').values=[['Synthetic borrowers. Independent portfolio demonstration.']];
summary.getRange('C3').format.font={italic:true,color:colors.gray};
summary.getRange('C5').values=[['Case selected:']];summary.getRange('D5').formulas=[["='Assumptions'!D5"]];sourceLink(summary,'D5');
summary.getRange('D5:F5').format.borders={preset:'outside',style:'dotted',color:colors.teal};
summary.getRange('H5').values=[['Held-out snapshots']];summary.getRange('I5').values=[['2023–2024']];
summary.getRange('C7:D7').values=[['Portfolio measure','Active case']];header(summary,'C7:D7');
summary.getRange('C8:C12').values=[['Borrowers'],['Debt / EAD proxy (CNY m)'],['Debt-weighted PD'],['Expected loss proxy (CNY m)'],['Average PD']];
summary.getRange('D8:D12').formulas=[['=COUNTA(Scoring!A'+first+':A'+last+')'],['=SUM(Scoring!C'+first+':C'+last+')'],['=SUMPRODUCT(Scoring!C'+first+':C'+last+',Scoring!N'+first+':N'+last+')/D9'],['=SUM(Scoring!P'+first+':P'+last+')'],['=AVERAGE(Scoring!N'+first+':N'+last+')']];
fmt(summary,'D8','#,##0');fmt(summary,'D9',money);fmt(summary,'D10',pct);fmt(summary,'D11',money);fmt(summary,'D12',pct);
summary.getRange('C11:D11').format.fill=colors.light;summary.getRange('C11:D11').format.font.bold=true;
summary.getRange('H7:K7').values=[['Test model','ROC-AUC','Brier','F1']];header(summary,'H7:K7');
const metrics=metricRows.filter(r=>(r.split??r.dataset??'test').toLowerCase()==='test');
function mval(r,k){return Number(r[k]??r[k.replace('_','')]??NaN);}
summary.getRange('H8:K9').values=[0,1].map(i=>{const r=metrics[i]||metricRows[i]||{};return [r.model??r.model_name??`Model ${i+1}`,mval(r,'roc_auc'),mval(r,'brier_score')||mval(r,'brier'),mval(r,'f1')];});
fmt(summary,'I8:K9','0.000');summary.getRange('H11').values=[['Observed default rate']];summary.getRange('I11').formulas=[['=AVERAGE(Source!L'+first+':L'+last+')']];fmt(summary,'I11',pct);
summary.getRange('H12').values=[['LGD assumption']];summary.getRange('I12').formulas=[["='Assumptions'!D31"]];fmt(summary,'I12',pct);
summary.getRange('C15:F15').values=[['Active risk band','Borrowers','Debt (CNY m)','Avg. PD']];header(summary,'C15:F15');
const bands=['Low','Moderate','Elevated','High'];summary.getRange('C16:C19').values=bands.map(x=>[x]);
summary.getRange('D16:F19').formulas=bands.map((_,i)=>{const r=i+16;return [`=COUNTIFS(Scoring!$O$${first}:$O$${last},C${r})`,`=SUMIFS(Scoring!$C$${first}:$C$${last},Scoring!$O$${first}:$O$${last},C${r})`,`=IF(D${r}=0,"n.a.",AVERAGEIFS(Scoring!$N$${first}:$N$${last},Scoring!$O$${first}:$O$${last},C${r}))`];});
fmt(summary,'D16:D19','#,##0');fmt(summary,'E16:E19',money);fmt(summary,'F16:F19',pct);
summary.getRange('C21').values=[['PD bands: <5%, <15%, <30%, 30% or above.']];summary.getRange('C21').format.font={italic:true,color:colors.gray};
const sectors=[...new Set(data.map(r=>r.sector))].sort();
summary.getRange('H15:K15').values=[['Sector','Borrowers','Avg. PD','Loss (CNY m)']];header(summary,'H15:K15');
summary.getRange(`H16:H${15+sectors.length}`).values=sectors.map(v=>[v]);
summary.getRange(`I16:K${15+sectors.length}`).formulas=sectors.map((_,i)=>{const r=16+i;return [`=COUNTIFS(Scoring!$B$${first}:$B$${last},H${r})`,`=AVERAGEIFS(Scoring!$N$${first}:$N$${last},Scoring!$B$${first}:$B$${last},H${r})`,`=SUMIFS(Scoring!$P$${first}:$P$${last},Scoring!$B$${first}:$B$${last},H${r})`];});
fmt(summary,`I16:I${15+sectors.length}`,'#,##0');fmt(summary,`J16:J${15+sectors.length}`,pct);fmt(summary,`K16:K${15+sectors.length}`,money);
const chart=summary.charts.add('bar',summary.getRange('C15:D19'));chart.title='Borrowers by active risk band';chart.hasLegend=false;chart.setPosition('C24','K39');chart.titleTextStyle.typeface='Arial';chart.titleTextStyle.fontSize=13;chart.series.items[0].fill=colors.teal;chart.xAxis={axisType:'textAxis',textStyle:{typeface:'Arial',fontSize:11}};chart.yAxis={numberFormatCode:'#,##0',numberFormatSourceLinked:false,textStyle:{typeface:'Arial',fontSize:11}};
summary.getRange('C41').values=[['Change Assumptions!D4 to explore a scenario. All calculations use the same held-out borrower cohort.']];
summary.getRange('C42').values=[['Debt is an illustrative EAD proxy; loss = debt × PD × fixed LGD.']];summary.getRange('C43').values=[['Cohort debt combines 2023–2024 snapshots; it is not a loan-book balance at one date.']];summary.getRange('C41:K43').format.font={size:10,color:colors.gray};

title(assumptions,'Scenario assumptions');
assumptions.getRange('C4').values=[['Case number']];assumptions.getRange('D4').values=[[1]];input(assumptions,'D4');assumptions.getRange('D4').dataValidation={rule:{type:'list',values:['1','2','3']}};
assumptions.getRange('C5').values=[['Case selected:']];assumptions.getRange('D5').formulas=[['=CHOOSE(D4,"Base","Adverse","Severe")']];assumptions.getRange('F4').values=[['1 = Base    2 = Adverse    3 = Severe']];
assumptions.getRange('C7:F7').values=[['Driver','Value','Units','Treatment']];header(assumptions,'C7:F7');assumptions.getRange('F1:F48').format.columnWidth=32;assumptions.getRange('E1:E48').format.columnWidth=20;
const drivers=[['Leverage shock',0,.05,.10,'ratio points','Add; cap adjusted ratio to [0,1]'],['DSCR change',0,-.15,-.30,'relative change','Multiply baseline DSCR by 1 + shock'],['Borrowing rate shock',0,1,2,'percentage points','Add to borrower rate'],['GDP growth shock',0,-2,-4,'percentage points','Add to GDP growth']];
drivers.forEach((d,i)=>{const r=8+i*5;assumptions.getRange(`C${r}:F${r}`).values=[[d[0],null,d[4],d[5]]];assumptions.getRange(`D${r}`).formulas=[[`=IF(CHOOSE($D$4,ISBLANK(D${r+1}),ISBLANK(D${r+2}),ISBLANK(D${r+3})),NA(),CHOOSE($D$4,D${r+1},D${r+2},D${r+3}))`]];assumptions.getRange(`C${r}:F${r}`).format.fill=colors.light;assumptions.getRange(`C${r}:F${r}`).format.font.bold=true;assumptions.getRange(`C${r+1}:D${r+3}`).values=[['Base',d[1]],['Adverse',d[2]],['Severe',d[3]]];input(assumptions,`D${r+1}:D${r+3}`);fmt(assumptions,`D${r}:D${r+3}`,i<2?'0.0%;(0.0%);–':'0.00;(0.00);–');});
assumptions.getRange('C30:F30').values=[['Global assumption','Value','Units','Definition']];header(assumptions,'C30:F30');assumptions.getRange('C31:F31').values=[['Loss given default',.45,'proportion','Illustrative fixed LGD']];input(assumptions,'D31');fmt(assumptions,'D31',pct);assumptions.getRange('D31').dataValidation={rule:{type:'decimal',operator:'between',formula1:0,formula2:1}};
assumptions.getRange('H7:K7').values=[['Frozen model term','Coefficient','Unit','Training']];header(assumptions,'H7:K7');
assumptions.getRange('H8:K13').values=['Intercept',...predictors].map((t,i)=>[t,beta[i],i===0?'log-odds':i===1?'ratio':i===2?'times':i===5?'0 / 1':'pp','2017–19']);fmt(assumptions,'I8:I13','0.000000');assumptions.getRange('H1:H48').format.columnWidth=25;
assumptions.getRange('H16').values=[['Source: outputs/coefficients.csv']];assumptions.getRange('H17').values=[['Five predictors; logistic MLE.']];assumptions.getRange('H19').values=[['Scenario design']];assumptions.getRange('H19').format.font.bold=true;assumptions.getRange('H20').values=[['Shocks are illustrative sensitivities.']];assumptions.getRange('H21').values=[['They are not macroeconomic forecasts.']];assumptions.getRange('H22').values=[['Past-due indicator remains unchanged.']];
assumptions.getRange('C34').values=[['Amber cells are editable. Blank selected drivers return an error; missing unselected cases do not affect the active case.']];assumptions.getRange('C35').values=[['Coefficients remain fixed. Re-run the pipeline and rebuild the workbook to change the fitted model.']];

standard(source,`A1:N${last}`);source.getRange('A1:N'+last).format.columnWidth=15;source.getRange('A1').values=[['Test-cohort source data']];source.getRange('A1').format.font={size:16,bold:true,color:colors.navy};source.getRange('A2').values=[['Source: outputs/test_predictions.csv. Synthetic data; one borrower at one snapshot.']];source.getRange('A3').values=[['Case selected:']];source.getRange('B3').formulas=[["='Assumptions'!D5"]];sourceLink(source,'B3');
const sourceHeaders=['Borrower ID','Sector','Debt (CNY m)','Leverage','DSCR','Rate (pp)','GDP (pp)','Past due 30d','Snapshot date','Python PD','Tree PD','Default 12m','Risk band','Split'];
source.getRange('A6:N6').values=[sourceHeaders];header(source,'A6:N6');
source.getRange(`A${first}:N${last}`).values=data.map(r=>[r.borrower_id,r.sector,+r.debt_cny_m,+r.leverage,+r.dscr,+r.interest_rate_pct,+r.gdp_growth_pct,+r.past_due_30d,new Date(r.snapshot_date+'T00:00:00Z'),+r.pd_logistic,+r.pd_tree,+r.default_12m,r.risk_band,r.split]);
source.getRange('B1:B'+last).format.columnWidth=20;fmt(source,`C${first}:C${last}`,money);fmt(source,`D${first}:D${last}`,pct);fmt(source,`E${first}:E${last}`,ratio);fmt(source,`F${first}:G${last}`,'0.00');fmt(source,`I${first}:I${last}`,'yyyy-mm-dd');fmt(source,`J${first}:K${last}`,pct);source.freezePanes.freezeRows(6);source.freezePanes.freezeColumns(2);source.tables.add(`A6:N${last}`,true,'CreditData').style='TableStyleMedium2';

standard(scoring,`A1:P${last}`);scoring.getRange(`A1:P${last}`).format.columnWidth=16;scoring.getRange(`B1:B${last}`).format.columnWidth=20;scoring.getRange('A1').values=[['Borrower-level scenario scoring']];scoring.getRange('A1').format.font={size:16,bold:true,color:colors.navy};scoring.getRange('A2').values=[['Logit = intercept + coefficient × predictor. PD = 1 / (1 + exp(−logit)).']];scoring.getRange('A3').values=[['Case selected:']];scoring.getRange('B3').formulas=[["='Assumptions'!D5"]];sourceLink(scoring,'B3');
scoring.getRange('A6:P6').values=[['Borrower ID','Sector','Debt (CNY m)','Base leverage','Base DSCR','Base rate (pp)','Base GDP (pp)','Past due 30d','Active leverage','Active DSCR','Active rate (pp)','Active GDP (pp)','Active logit','Active PD','Active risk band','Loss proxy (CNY m)']];header(scoring,'A6:P6');
scoring.getRange(`A${first}:P${last}`).formulas=data.map((_,i)=>{const r=i+first;return [`=Source!A${r}`,`=Source!B${r}`,`=Source!C${r}`,`=Source!D${r}`,`=Source!E${r}`,`=Source!F${r}`,`=Source!G${r}`,`=Source!H${r}`,`=MIN(1,MAX(0,D${r}+Assumptions!$D$8))`,`=E${r}*(1+Assumptions!$D$13)`,`=F${r}+Assumptions!$D$18`,`=G${r}+Assumptions!$D$23`,`=Assumptions!$I$8+I${r}*Assumptions!$I$9+J${r}*Assumptions!$I$10+K${r}*Assumptions!$I$11+L${r}*Assumptions!$I$12+H${r}*Assumptions!$I$13`,`=1/(1+EXP(-M${r}))`,`=IF(N${r}<0.05,"Low",IF(N${r}<0.15,"Moderate",IF(N${r}<0.30,"Elevated","High")))`,`=C${r}*N${r}*Assumptions!$D$31`];});
sourceLink(scoring,`A${first}:M${last}`);sourceLink(scoring,`P${first}:P${last}`);fmt(scoring,`C${first}:C${last}`,money);fmt(scoring,`D${first}:D${last}`,pct);fmt(scoring,`I${first}:I${last}`,pct);fmt(scoring,`E${first}:E${last}`,ratio);fmt(scoring,`J${first}:J${last}`,ratio);fmt(scoring,`F${first}:G${last}`,'0.00');fmt(scoring,`K${first}:M${last}`,'0.00');fmt(scoring,`N${first}:N${last}`,pct);fmt(scoring,`P${first}:P${last}`,money);scoring.getRange(`N${first}:N${last}`).conditionalFormats.add('colorScale',{colors:['#E4F1E9','#F8E3A4','#D78578'],thresholds:['min',{type:'num',value:.15},'max']});scoring.freezePanes.freezeRows(6);scoring.freezePanes.freezeColumns(2);scoring.tables.add(`A6:P${last}`,true,'ScoringData').style='TableStyleMedium2';

standard(checks,`C1:F${14+n}`);checks.getRange(`F1:F${14+n}`).format.columnWidth=26;
title(checks,'Scoring reconciliation');checks.getRange('C4').values=[['Case selected:']];checks.getRange('D4').formulas=[["='Assumptions'!D5"]];sourceLink(checks,'D4');checks.getRange('C6:F6').values=[['Check','Difference','Tolerance','Scope']];header(checks,'C6:F6');
checks.getRange('C7:C10').values=[['Borrower count'],['Debt control (CNY m)'],['Maximum baseline PD error'],['Baseline comparison']];
checks.getRange('D7:D10').formulas=[[`=COUNTA(Scoring!A${first}:A${last})-COUNTA(Source!A${first}:A${last})`],[`=SUM(Scoring!C${first}:C${last})-SUM(Source!C${first}:C${last})`],[`=IF(Assumptions!D4=1,MAX(F15:F${14+n}),"n.a.")`],['=IF(Assumptions!D4=1,"Base case only","Select Base to compare")']];checks.getRange('E7:F9').values=[[0,'All cases'],[1e-8,'All cases'],[1e-10,'Default Base drivers']];fmt(checks,'D7:E8','0.00');fmt(checks,'D9:E9','0.00E+00');
checks.getRange('C12').values=[['Compare original Base inputs. Edited Base assumptions change reconciliation.']];
checks.getRange('C14:F14').values=[['Borrower ID','Python baseline PD','Workbook active PD','Absolute difference']];header(checks,'C14:F14');
checks.getRange(`C15:F${14+n}`).formulas=data.map((_,i)=>{const s=i+first,r=i+15;return [`=Source!A${s}`,`=Source!J${s}`,`=Scoring!N${s}`,`=IF(Assumptions!$D$4=1,ABS(D${r}-E${r}),"n.a.")`];});fmt(checks,`D15:E${14+n}`,pct);fmt(checks,`F15:F${14+n}`,'0.00E+00');checks.getRange(`F15:F${14+n}`).conditionalFormats.add('cellIs',{operator:'greaterThan',formula:1e-10,format:{fill:'#FCE2DF',font:{color:colors.red,bold:true}}});checks.getRange('D7:D8').conditionalFormats.addCustom('ABS(D7)>E7',{fill:'#FCE2DF',font:{color:colors.red,bold:true}});checks.freezePanes.freezeRows(14);

// Verify formula calculations and selected-case dependency changes before export.
wb.recalculate();
const basePD=summary.getRange('D12').values[0][0],baseEL=summary.getRange('D11').values[0][0];
const expectedPD=data.reduce((s,r)=>s+Number(r.pd_logistic),0)/n;
const expectedEL=data.reduce((s,r)=>s+Number(r.debt_cny_m)*Number(r.pd_logistic)*.45,0);
if(!Number.isFinite(basePD)||!Number.isFinite(baseEL)||Math.abs(basePD-expectedPD)>1e-10||Math.abs(baseEL-expectedEL)>1e-6)throw new Error(`Baseline mismatch ${basePD}/${expectedPD}, ${baseEL}/${expectedEL}`);
assumptions.getRange('D4').values=[[2]];wb.recalculate();const adversePD=summary.getRange('D12').values[0][0];if(!(adversePD>basePD))throw new Error('Adverse scenario did not increase PD');
const prior=assumptions.getRange('D24').values[0][0];assumptions.getRange('D24').values=[[null]];wb.recalculate();if(!Number.isFinite(summary.getRange('D12').values[0][0]))throw new Error('Unselected blank changed active scenario');assumptions.getRange('D24').values=[[prior]];
const activePrior=assumptions.getRange('D25').values[0][0];assumptions.getRange('D25').values=[[null]];wb.recalculate();if(Number.isFinite(summary.getRange('D12').values[0][0]))throw new Error('Selected blank failed to propagate');assumptions.getRange('D25').values=[[activePrior]];
assumptions.getRange('D4').values=[[1]];wb.recalculate();
const errorScan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:20},summary:'Final error scan',maxChars:2000});
console.log(errorScan.ndjson);
console.log(JSON.stringify({rows:n,basePD,expectedPD,baseEL,expectedEL,adversePD,maxPDError:checks.getRange('D9').values[0][0]}));
console.log((await wb.inspect({kind:'table',range:'Summary!C7:K12',include:'values,formulas',tableMaxRows:6,tableMaxCols:9,maxChars:2500})).ndjson);
for(const [name,range] of [['Summary','B1:K43'],['Assumptions','B1:K36'],['Scoring','A1:P15'],['Source','A1:N15'],['Checks','B1:F22']]){
  const png=await wb.render({sheetName:name,range,scale:1.5,format:'png'});await fs.writeFile(path.join(outputDir,`${name.toLowerCase()}.png`),new Uint8Array(await png.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(path.join(outputDir,'Credit_Risk_Review.xlsx'));
await fs.copyFile(path.join(outputDir,'Credit_Risk_Review.xlsx'),path.join(repo,'outputs','Credit_Risk_Review.xlsx'));
await fs.copyFile(path.join(outputDir,'summary.png'),path.join(repo,'outputs','charts','workbook_preview.png'));
await fs.writeFile(path.join(outputDir,'verification.json'),JSON.stringify({rows:n,basePD,expectedPD,baseEL,expectedEL,adversePD,maxPDError:checks.getRange('D9').values[0][0],nativeExcelVerified:false},null,2));
