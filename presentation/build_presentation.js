/* Rebuild: npm install pptxgenjs && node build_presentation.js
   Bundled runtime fallback is used on the author's workstation. */
const fs = require('fs');
const path = require('path');
let PptxGenJS;
try { PptxGenJS = require('pptxgenjs'); }
catch { PptxGenJS = require('C:/Users/conra/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/pptxgenjs'); }
const pptx = new PptxGenJS();
pptx.layout='LAYOUT_WIDE'; pptx.author='Conrad Compagna'; pptx.subject='PetrIUS postdoctoral interview: Tasks I, III and IV';
pptx.title='From printed page to historical evidence'; pptx.company='PetrIUS interview materials';
pptx.lang='en-GB'; pptx.theme={headFontFace:'Aptos Display',bodyFontFace:'Aptos',lang:'en-GB'};
const C={bg:'F4F1E9',ink:'162B38',muted:'566570',teal:'087F8C',green:'239B76',gold:'CB9133',plum:'935BA5',red:'B14E4A',line:'D9DED9',white:'FFFFFF',pale:'E3EEEA'};
const asset=n=>path.join(__dirname,'assets',n);
const metrics=JSON.parse(fs.readFileSync(path.join(__dirname,'metrics.json'),'utf8'));
const script=[];
function text(s,t,x,y,w,h,size=20,color=C.ink,bold=false,opts={}){s.addText(t,{x,y,w,h,fontFace:'Aptos',fontSize:size,color,bold,margin:0,breakLine:false,vertAnchor:'mid',...opts});}
function rect(s,x,y,w,h,fill=C.white,line=fill,r=0){s.addShape(r?pptx.ShapeType.roundRect:pptx.ShapeType.rect,{x,y,w,h,rectRadius:r,fill:{color:fill},line:{color:line,width:0.7},radius:r});}
function line(s,x1,y1,x2,y2,color=C.line,width=1){s.addShape(pptx.ShapeType.line,{x:x1,y:y1,w:x2-x1,h:y2-y1,line:{color,width}});}
function arrow(s,x1,y1,x2,y2,color=C.teal,width=2){s.addShape(pptx.ShapeType.line,{x:Math.min(x1,x2),y:Math.min(y1,y2),w:Math.abs(x2-x1),h:Math.abs(y2-y1),flipH:x2<x1,flipV:y2<y1,line:{color,width,beginArrowType:'none',endArrowType:'triangle'}});}
const imageSizes=JSON.parse(fs.readFileSync(path.join(__dirname,'asset_sizes.json'),'utf8'));
function img(s,n,x,y,w,h){const [iw,ih]=imageSizes[n], scale=Math.min(w/iw,h/ih), dw=iw*scale,dh=ih*scale;s.addImage({path:asset(n),x:x+(w-dw)/2,y:y+(h-dh)/2,w:dw,h:dh});}
function pill(s,t,x,y,w,color=C.teal){rect(s,x,y,w,.32,color);text(s,t,x+.08,y+.03,w-.16,.25,10,C.white,true);}
function newSlide(section,title,sub='',dark=false){const s=pptx.addSlide();s.background={color:dark?C.ink:C.bg};s._dark=dark;s._title=title;s._section=section;
  text(s,section.toUpperCase(),.55,.35,11,.28,11,dark?'8BD4D2':C.teal,true,{charSpacing:1.5});
  text(s,title,.55,.92,12.25,.83,32,dark?C.white:C.ink,true);
  if(sub)text(s,sub,.58,1.78,12.05,.46,15,dark?'D3E1E4':C.muted);
  line(s,.55,7.08,12.78,7.08,dark?'34515E':C.line,.8);
  text(s,'CONRAD COMPAGNA  /  PETRIUS',.55,7.18,9,.18,8,dark?'B5C7CF':C.muted,true,{charSpacing:.9});
  text(s,String(pptx._slides.length).padStart(2,'0'),12.18,7.12,.6,.3,10,dark?'B5C7CF':C.muted,false,{align:'right'});
  return s;
}
function notes(s,body,source,duration=60){const i=pptx._slides.length;const task=i<=5?'Task I':i<=10?'Task III':'Task IV';
  s.addNotes(`${task} | ${duration} seconds | ${i<=15?'Slide '+((i-1)%5+1)+' of 5':'Appendix'}\n\n${body}\n\nEvidence: ${source}`);
  if(i<=15)script.push({slide:i,task,title:s._title,seconds:duration,body,source});
}
function label(s,a,b,x,y,w=3.75){text(s,a,x,y,w,.5,27,C.ink,true);text(s,b,x,y+.62,w,1.1,16,C.muted);}
function card(s,t,b,x,y,w,h=1.1,col=C.teal){rect(s,x,y,w,h,C.white);rect(s,x,y,.055,h,col);text(s,t,x+.18,y+.14,w-.36,.28,17,C.ink,true);text(s,b,x+.18,y+.51,w-.36,h-.59,13,C.muted);}

// I.1 — two original pages, complete images, no decorative substitute.
{
 const s=newSlide('Task I · 1 / 5','The two-page task: 131 / 131 correct','Rome, 1582 · Decretals · MDZ bsb10144443 · scans 40 and 41');
 img(s,'minimal_40.jpg',.55,2.37,3.4,4.31);img(s,'minimal_41.jpg',4.02,2.37,3.4,4.31);
 [['text','3CA03C'],['summarium','0078C8'],['inscriptio','A000A0'],['other','DC0000']].forEach((r,i)=>{rect(s,.70+i*1.76,6.81,.12,.12,r[1]);text(s,r[0],.91+i*1.76,6.76,1.42,.22,10,C.muted);});
 text(s,'A complete, reproducible submission',8.02,2.55,4.54,.86,26,C.ink,true);
 text(s,'Fetch images + hOCR\nFind the two central blocks\nAssign the four requested roles\nExport overlays + evaluation',8.02,3.6,4.54,1.8,20,C.ink,false,{breakLine:false,paraSpaceAfter:12});
 pill(s,'PERSONALLY CHECKED AGAINST BOTH PAGES',8.02,5.75,4.58);
 text(s,'OpenCV + NumPy · no training required',8.02,6.26,4.45,.4,14,C.muted);
 notes(s,`My starting point is the assignment itself: these two pages of the Roman Decretals. The submitted minimal program retrieves both images and both hOCR files directly from MDZ, finds the central text blocks, assigns the four requested roles, and produces these colour overlays together with the evaluation. It scores 131 out of 131 against the reference, and I personally inspected both page overlays. The colours separate legal text, summaria, inscriptiones and other material. The surrounding gloss remains outside the selected blocks. The implementation needs only OpenCV and NumPy. I have included this small program because the committee should be able to run and inspect the actual task solution immediately.`, 'task1_min/task1.py; task1_min/reference.csv; task1_min/labels_00040.jpg; task1_min/labels_00041.jpg');
}
// I.2
{
 const s=newSlide('Task I · 2 / 5','A small rule system is sufficient for this edition','The visual distinctions stated in the brief become explicit measurements.');
 const rows=[['Red ink','other','DC0000'],['Slanted type','summarium','0078C8'],['Large black type','text','3CA03C'],['Remaining small type','inscriptio',C.plum]];
 rows.forEach((r,i)=>{rect(s,.6,2.5+i*.81,5.5,.65,C.white);text(s,r[0],.82,2.66+i*.81,2.72,.27,18);arrow(s,3.62,2.82+i*.81,4.03,2.82+i*.81,r[2]);text(s,r[1],4.22,2.66+i*.81,1.67,.27,18,r[2],true);});
 text(s,'Reference → program',6.73,2.36,5.4,.3,14,C.muted);
 const names=['text','summ.','inscr.','other','outside'], nums=[60,16,7,6,42];
 names.forEach((n,i)=>text(s,n,8.10+i*.85,2.92,.8,.3,12,C.muted,true,{align:'center'}));
 names.forEach((n,i)=>{text(s,n,6.7,3.46+i*.49,1.24,.3,13,C.ink,true);names.forEach((_,j)=>{rect(s,8.1+j*.85,3.34+i*.49,.8,.43,i===j?C.teal:C.white);text(s,String(i===j?nums[i]:0),8.1+j*.85,3.43+i*.49,.8,.25,15,i===j?C.white:C.muted,i===j,{align:'center'});});});
 text(s,'Also labelled: gutter numbers + initial',.64,6.03,5.8,.46,18,C.ink,true);
 text(s,'131 checked labels · all diagonal',6.74,6.03,5.35,.45,21,C.teal,true);
 text(s,'Adaptive thresholding · split gutter-crossing OCR lines · grow each block to its chapter head',.64,6.53,12,.33,14,C.muted);
 notes(s,`There are three measurements: red ink, slant, and letter height relative to the page's usual type. Large black lines establish the central blocks. The program extends each block upwards and downwards to include its chapter heads, and rejects lines extending into the gloss. Red material becomes other; slanted type becomes summarium; large type becomes text; the remaining small type becomes inscriptio. It uses the library's word and line geometry, splitting the five OCR lines that cross the gutter. The matrix contains sixty text labels, sixteen summaria, seven inscriptiones, six other labels, and forty-two outside controls. All are correct. The completed program also labels six gutter numbers and the woodcut initial, and rejects two junk OCR fragments. This solves the specified pages with a compact, inspectable implementation.`, 'task1_min/task1.py; task1_min/reference.csv; minimal confusion matrix verified in source');
}
// I.3
{
 const s=newSlide('Task I · 3 / 5','Across editions, use learned page and line models','D-FINE finds regions. PERO reads inside them. The neural tagger assigns roles.');
 const labels=[['D-FINE','region detection'],['PERO','lines + recognition'],['Neural v3','region + line roles']];
 labels.forEach((r,i)=>{card(s,r[0],r[1],.63+i*3.25,2.53,2.75,1.02);if(i<2)arrow(s,3.46+i*3.25,3.04,3.78+i*3.25,3.04);});
 img(s,'neural_40.jpg',10.18,2.42,2.56,4.44);
 label(s,'120 pages','Region dataset\n100 training + 20 evaluation',.68,4.13,4.1);
 label(s,'120 pages','Role dataset\n100 training + 20 evaluation',5.10,4.13,4.35);
 text(s,'Line image + OCR characters + position + page context',.68,6.22,8.7,.58,22,C.teal,true);
 notes(s,`The cross-edition solution is a neural pipeline. Fixed rules depend on the relationship between text size, gloss size, spacing and position in one edition. Those relationships change between printers and typefaces. I therefore trained D-FINE to find the regions, constrained PERO to find and recognise lines within those regions, and trained a neural model to select the central blocks and assign line roles. The line model combines colour image strips, OCR characters, coordinates and the other lines on the page. The two training collections each contain one hundred training pages and twenty evaluation pages. This image shows the combined pipeline on an original interview page. The package contains its model weights, inference code and a viewer for inspecting the results.`, 'out/dfine_region_training_v1/data_manifest.json; out/central_block_annotations_v1/manifest.json; line_nn_v3/model.py; out/line_nn_v3/task_predictions/bsb10144443/00040.json');
}
// I.4
{
 const s=newSlide('Task I · 4 / 5','The trained systems have measurable results','The two evaluations answer different questions: finding regions and assigning roles.');
 text(s,'REGIONS · D-FINE',.63,2.44,5.65,.3,13,C.teal,true);
 text(s,'0.862',.65,2.93,3.1,.78,52,C.ink,true);text(s,'region F1 at IoU ≥ 0.50',.68,3.84,5.5,.43,20);
 text(s,'20 evaluation pages from 20 other books\n206 matched · 32 extra · 34 missed regions',.68,4.54,5.52,.95,17,C.muted);
 text(s,'ROLE LABELS · NEURAL v3',6.95,2.44,5.62,.3,13,C.teal,true);
 ['Text','Summarium','Inscriptio','Other'].forEach((n,i)=>{const yy=3.08+i*.59; text(s,n,6.96,yy,1.64,.27,16);rect(s,8.63,yy+.01,2.91,.27,'E0E6E3');rect(s,8.63,yy+.01,2.91*metrics.v3_f1[i],.27,[C.teal,C.green,C.plum,C.gold][i]);text(s,(metrics.v3_f1[i]*100).toFixed(1)+'%',11.76,yy,1,.3,15,C.ink,true);});
 text(s,'0.945 macro-F1 · 20 evaluation pages\n14 label errors among 5,065 supplied lines',6.96,5.70,5.75,.86,19,C.teal,true);
 text(s,'Training priorities: small source labels, chapter apparatus and precise region boundaries.',.67,6.68,12,.28,14,C.muted);
 notes(s,`These results identify what each stage accomplishes and what to improve next. The region detector reaches an F1 score of 0.862 at fifty percent overlap on twenty pages from twenty books outside its training books. That represents 206 matched regions, thirty-two extra detections and thirty-four missed regions. The neural role model reaches macro-F1 of 0.945 on its twenty evaluation pages. Its text and summarium F1 scores are approximately ninety-nine percent; inscriptio and other are approximately ninety percent. There are fourteen label errors among 5,065 supplied lines. The practical next steps are clear: improve small source labels, chapter apparatus and region boundaries, then extend the labelled examples to Gothic and mixed-script material.`, 'D-FINE epoch14/step1400 in out/dfine_region_training_v1/full/epoch_metrics.jsonl; line_nn_v3/work/result_train_full.json; line_nn_v3/work/train_full.log');
}
// I.5
{
 const s=newSlide('Task I · 5 / 5','Six days: a complete experimental environment','LLM agents made this breadth of implementation and testing possible.',true);
 [['100','volumes inventoried'],['26k+','source lines'],['200+','source files'],['3','neural versions']].forEach((r,i)=>{text(s,r[0],.68+i*3.14,2.64,2.82,.76,45,'8BD4D2',true);text(s,r[1],.71+i*3.14,3.48,2.74,.53,16,C.white);});
 line(s,.71,4.28,12.52,4.28,'45606C');
 text(s,'Acquire → annotate → train → evaluate → inspect → revise',.71,4.7,11.86,.64,26,C.white,true);
 text(s,'Claude + Codex: implementation, debugging and experiments\nChatGPT: training annotations\nMy work: research direction, decisions and personal checking',.73,5.55,11.74,1.03,20,'D3E1E4');
 notes(s,`I used LLM agents extensively, and that is central to how this work was done. In six days I developed an acquisition layer for a hundred volumes, more than twenty-six thousand source lines across more than two hundred files, a review viewer, labelled training collections, a trained region detector and three generations of neural classifiers. Multiple candidate systems were tested and rejected. Claude and Codex implemented code, ran experiments and investigated failures under my direction. ChatGPT generated the training annotations, which I reviewed. I set the questions, judged the results and personally check the submission. This is a modern research workflow: it gives one researcher the implementation capacity and experimental breadth that previously demanded a much larger effort.`, 'FINDINGS.md section12; out/webgpt_ocr_fullpage100_20261006/timeline_evidence.json; project source inventory; NOTE.md tools statement');
}
// III.1
{
 const s=newSlide('Task III · 1 / 5','The same divisio; a different attribution','D. 1.1.1pr · the supplied witnesses, Venice 1490 and Lyon 1627');
 img(s,'divisio_1490.png',.68,2.61,5.77,2.18);img(s,'divisio_1627.png',6.86,2.61,5.77,2.18);
 pill(s,'1490',.7,2.18,1.05);pill(s,'1627',6.88,2.18,1.05);
 text(s,'Jac. de arena … Bar.',.76,5.05,5.45,.6,29,C.ink,true);
 text(s,'B.',6.96,5.05,5.45,.6,29,C.ink,true);
 text(s,'Jacobus de Arena + Bartolus',.76,5.83,5.45,.45,21,C.muted);
 text(s,'Bartolus',6.96,5.83,5.45,.45,21,C.muted);
 text(s,'The historical event to detect: Jacobus de Arena disappears from the attribution.',.75,6.61,11.9,.33,17,C.red,true);
 notes(s,`The supplied example makes the historical objective concrete. These are crops of the complete divisio in the left column of each image. In 1490 the text names Jacobus de Arena and ends with Bartolus. In 1627 it retains only Bartolus. We need a system that retrieves these two units, recognises them as versions of the same paratext, and records the loss of an attribution. The abbreviation Bar and the abbreviation B should resolve to the same person. Jac de arena must remain a separate attribution that can disappear. This is why a single fuzzy text similarity score is insufficient. The workflow must distinguish variation in written form from changes in the information communicated by the paratext.`, 'PetrIUS Interview Tasks for the Postdoc 4 Position.docx, Task III; D. 1.1.1. 1490.jpg; D. 1.1.1. 1627.jpg');
}
// III.2
{
 const s=newSlide('Task III · 2 / 5','Retrieve the legal locus, then recover its paratext','An edition-independent anchor connects different page layouts.');
 const st=[['1  Anchor','D. 1.1.1pr\nBook / title / fragment / incipit'],['2  Retrieve','OCR character n-grams\nRapidFuzz: fuzzy text matching'],['3  Attach','Layout + lemma + sequence\nFind the neighbouring divisio'],['4  Assemble','Join lines into a whole unit\nKeep image coordinates']];
 st.forEach((r,i)=>{card(s,r[0],r[1],.67+i*3.17,2.8,2.74,2.02);if(i<3)arrow(s,3.48+i*3.17,3.77,3.76+i*3.17,3.77);});
 rect(s,.68,5.4,11.97,1.09,C.pale);text(s,'Unit key',.9,5.62,1.54,.32,17,C.teal,true);text(s,'edition × legal locus × paratext type × occurrence',2.61,5.58,9.68,.43,24,C.ink,true);
 notes(s,`I begin with an edition-independent legal identifier, here D.1.1.1pr. I retrieve the corresponding passage using the OCR, book and title headings, incipits, and RapidFuzz for character-level fuzzy matching. This gives a local search area even when spelling and abbreviations differ. Within that area, the page model identifies the text streams. A unit classifier uses the lemma, position and neighbouring material to attach the divisio to the fragment. It assembles a complete unit across lines and, where needed, across page breaks. Each result receives a stable key combining edition, legal locus, paratext type and occurrence. The record retains the original image coordinates and raw OCR, so every later comparison can be checked against the actual witness.`, 'Proposed workflow for Task III; RapidFuzz official documentation: https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html ; existing implementation components: region_dataset/, line_nn_v3/, annotation_viewer/');
}
// III.3
{
 const s=newSlide('Task III · 3 / 5','Compare wording and historical content separately','Normalize for matching; preserve the evidence needed to detect change.');
 card(s,'Diplomatic layer','Raw OCR → checked reading → image link',.7,2.56,11.95,.98);
 arrow(s,6.67,3.63,3.58,4.14);arrow(s,6.67,3.63,9.62,4.14);
 card(s,'Matching layer','Abbreviation alternatives · long-s / u-v\nCollateX alignment · candidate similarity',.7,4.27,5.69,1.23,C.teal);
 card(s,'Content layer','Names · legal citations · negation\nConditions · exceptions · attribution',6.96,4.27,5.69,1.23,C.plum);
 text(s,'Bar. ↔ B. → Bartolus',.91,5.91,5.24,.55,25,C.teal,true);
 text(s,'Jac. de arena → Jacobus de Arena',7.11,5.91,5.31,.55,20,C.plum,true);
 text(s,'Cluster aligned variants; keep every deletion of a name or qualification visible.',.78,6.65,12,.32,16,C.muted);
 notes(s,`I keep a diplomatic layer and derive two representations from it. The matching layer handles spelling variation, long s, u and v, and alternative abbreviation expansions. Character n-grams retrieve candidates; CollateX then exposes correspondences in a multiple-witness alignment. The content layer records named authorities, citations, negation, conditions and exceptions. A controlled authority list resolves Bar and B to Bartolus, while retaining the printed forms and locations. Candidate units are grouped through aligned similarity and shared legal locus, then checked for conflicting content fields before they become a variant group. Crucially, normalisation never deletes an author or a qualification. A name disappearing is therefore an event to inspect, rather than noise that a high similarity score silently removes.`, 'Proposed Task III workflow; CollateX official documentation: https://collatex.net/doc/ ; source example from the interview task document and supplied images');
}
// III.4
{
 const s=newSlide('Task III · 4 / 5','Make the change an explicit, inspectable record','One aligned unit; two resolved authority sets; one deletion event.');
 text(s,'1490',.74,2.56,1.7,.4,23,C.teal,true);text(s,'1627',7.54,2.56,1.7,.4,23,C.teal,true);
 card(s,'Jacobus de Arena','Printed: Jac. de arena',.76,3.26,4.82,.99,C.plum);
 card(s,'Bartolus','Printed: Bar.',.76,4.51,4.82,.99,C.teal);
 card(s,'Bartolus','Printed: B.',7.56,4.51,4.82,.99,C.teal);
 arrow(s,5.72,4.99,7.34,4.99);line(s,5.72,3.76,6.59,3.76,C.red,3);text(s,'×',6.66,3.43,.65,.65,32,C.red,true);
 text(s,'ATTRIBUTION REMOVED',7.55,3.32,4.74,.55,22,C.red,true);
 rect(s,.76,5.98,11.62,.67,C.pale);text(s,'Event: D.1.1.1pr / divisio / Jacobus de Arena / present in 1490 → absent in 1627',.98,6.16,11.20,.31,16,C.ink,true);
 notes(s,`This is the structured result I want. The 1490 authority set contains Jacobus de Arena and Bartolus; the 1627 set contains Bartolus. Alignment links the shared division of the passage, so the remaining difference becomes an attribution-removal event with an edition, a locus and a paratext type. The record stores both excerpts, the exact source spans and the reason for the flag. The same mechanism can flag a lost exception, a changed negation or an added legal reference. It does not equate every textual difference with a doctrinal difference. Historians assign the interpretation in the review interface. The computer's contribution is systematic detection and comparison of these events across thousands of corresponding units.`, 'Proposed output schema; the named-author difference is specified in Task III and visible in both source images');
}
// III.5
{
 const s=newSlide('Task III · 5 / 5','Return evidence to historians—and patterns to research','Proposed comparison desk: link each event to both witnesses.');
 rect(s,.7,2.52,7.6,3.77,C.white);rect(s,.7,2.52,7.6,.48,C.ink);text(s,'D. 1.1.1pr   /   divisio   /   attribution removed',.91,2.66,7.16,.2,12,C.white,true);
 img(s,'divisio_1490.png',.94,3.18,3.4,1.31);img(s,'divisio_1627.png',4.58,3.18,3.4,1.31);
 text(s,'1490: Jacobus de Arena; Bartolus\n1627: Bartolus',.99,4.73,6.96,.77,19);
 pill(s,'CONFIRM',1,5.69,1.41);pill(s,'CORRECT',2.58,5.69,1.48,C.plum);pill(s,'EXPORT EVIDENCE',4.24,5.69,2.31,C.ink);
 text(s,'Main risk',8.78,2.61,3.93,.44,24,C.red,true);
 text(s,'OCR loss masquerades\nas historical deletion.',8.78,3.22,3.93,1.18,25,C.ink,true);
 text(s,'Inspect the complete source unit;\nre-recognise or transcribe\nthe disputed span.',8.81,4.78,3.86,1.18,18,C.muted);
 text(s,'Research payoff: where, when and in which editorial families did attribution disappear?',.74,6.65,12,.31,16,C.teal,true);
 notes(s,`Historians see the two images, aligned diplomatic text, the resolved names and the proposed event side by side. They can confirm, correct and export a citable evidence record. The main risk is precise: a name missed by OCR can masquerade as a historical deletion. A missing-name flag therefore triggers inspection of the complete source unit, with targeted re-recognition or transcription of the disputed span. The unit boundary is checked too, because an attribution may sit on another line. Once events are confirmed, the analysis asks where, when and in which editorial families attribution disappears. That produces a corpus-wide history of editorial selection, while allowing every aggregate pattern to be traced back to its printed evidence.`, 'Task III requirements; proposed comparison interface, building on annotation_viewer/; no implemented variant-detection result is claimed');
}
// IV.1
{
 const s=newSlide('Task IV · 1 / 5','A 360-page pilot across six editions','1 December 2026 → 31 May 2027 · matched legal loci + contrasting page structures');
 const rows=[['Digest','Venice 1490','Gothic + gloss','60'],['Digest','Lyon 1569','Roman + gloss','60'],['Digest','Venice 1606','Roman + Greek notes','60'],['Digest','Lyon 1627','Roman + dense apparatus','60'],['Decretals','Venice 1494','Gothic + gloss','60'],['Decretals','Rome 1582','Roman + gloss','60']];
 ['Work','Edition','Purpose','Pages'].forEach((t,i)=>text(s,t,[.83,2.7,5.37,9.54][i],2.51,[1.5,2.4,3.8,1.1][i],.3,13,C.teal,true));
 rows.forEach((r,i)=>{rect(s,.7,2.96+i*.43,10.47,.38,i%2?C.bg:C.white);r.forEach((t,j)=>text(s,t,[.83,2.7,5.37,9.54][j],3.03+i*.43,[1.5,2.4,3.8,1.1][j],.24,15,j===3?C.teal:C.ink,j===3));});
 text(s,'40 Digest loci × 4 editions\n20 Decretals loci × 2 editions',.78,5.9,6.18,.72,22,C.ink,true);
 text(s,'240 train / 60 development / 60 test\nFreeze test pages before iteration.',7.10,5.91,5.55,.72,18,C.teal,true);
 notes(s,`I would start with three hundred and sixty complete pages: sixty from each of these six editions. The four Digest witnesses give a sequence from Gothic print in 1490 through Roman editions to 1627, including a witness with Greek notes. The two Decretals editions connect the task's successful Roman example to an earlier Gothic edition. I would select forty matched Digest loci across four witnesses and twenty Decretals loci across two, giving two hundred paratext witness units for direct comparison. The remaining page coverage supplies difficult layouts and continuation cases. The split is two hundred and forty training pages, sixty development pages and sixty sealed test pages. Adjacent pages of one sampled passage stay together in the same split.`, 'Pilot proposed here; edition metadata in corpus/benchmark_inventory.json: bsb00051759, bsb11396145, bsb10520013, heidelberg_justinian1627bd1, bsb00082927, bsb10144443');
}
// IV.2
{
 const s=newSlide('Task IV · 2 / 5','Historians define the units and the distinctions','Annotation concentrates expertise on decisions with historical consequences.');
 const tasks=[['Page structure','Regions · line order · continuation\nMain text / gloss / additions / paratext'],['Unit identity','Legal locus · lemma · paratext type\nWhere the unit begins and ends'],['Text and meaning','Names · citations · abbreviation readings\nAttribution · conditions · exceptions']];
 tasks.forEach((r,i)=>card(s,r[0],r[1],.74+i*4.18,2.64,3.83,1.83,[C.teal,C.plum,C.gold][i]));
 text(s,'Draft → correct → discuss disagreements → update the guide',.81,4.98,11.97,.57,25,C.teal,true);
 text(s,'December: 12-page calibration workshop\nWeekly: focused review clinic + annotated examples\nEvaluation: double-review 60 focal units, then adjudicate',.84,5.73,11.86,.98,19,C.ink);
 notes(s,`I need three kinds of historian input. First, page structure: the text streams, their reading order and where they continue. Second, unit identity: the legal locus, the paratext type and the exact boundaries of the unit. Third, text and meaning: difficult abbreviation readings, names, citations and whether a difference changes an attribution, condition or exception. We begin with a twelve-page calibration workshop covering all six editions. I prefill annotations with the existing models; historians correct them in the viewer and discuss disagreements in a short weekly clinic. Their decisions become examples in a living annotation guide. Sixty focal paratext units receive two independent readings and an adjudication, creating a focused reference for the historical event detection.`, 'Proposed collaboration protocol; existing annotation tools in annotation_viewer/ and region_dataset/');
}
// IV.3
{
 const s=newSlide('Task IV · 3 / 5','Six months, with a usable result at each stage','The existing software becomes the starting point for the pilot.');
 const months=['DEC','JAN','FEB','MAR','APR','MAY']; months.forEach((m,i)=>text(s,m,5.24+i*1.19,2.49,1.05,.3,13,C.teal,true,{align:'center'}));
 const bars=[['Corpus + rights + guide',0,2,C.teal],['Regions + line roles',1,2,C.teal],['OCR + Gothic / Greek',1,3,C.plum],['Locus + unit linking',2,2,C.gold],['Variants + historian review',3,2,C.plum],['Sealed evaluation + release',4,2,C.teal]];
 bars.forEach((r,i)=>{const y=3.06+i*.49;text(s,r[0],.78,y,4.15,.32,16);rect(s,5.31,y+.02,7.02,.29,'DFE5E1');rect(s,5.31+r[1]*1.17,y+.02,r[2]*1.17-.06,.29,r[3]);});
 text(s,'End January: checked pilot data\nEnd March: linked paratexts',.83,6.33,5.86,.53,16,C.muted);
 text(s,'End May: tested variant workflow\n+ first attribution-change study',7.15,6.33,5.22,.53,16,C.teal,true);
 notes(s,`December fixes the corpus, source terms and annotation guide. January produces a checked pilot dataset and a first retrained region and role pipeline. OCR work begins alongside it, concentrating on the Gothic and Greek examples and the fields needed for historical comparison. February and March develop legal-locus alignment and complete paratext assembly, including continuations. By the end of March, a historian can move from a locus to its corresponding units in the pilot editions. April adds variant grouping and attribution-change detection, reviewed in the comparison desk. May runs the sealed evaluation, packages the reproducible release and produces the first matched-locus study. Each stage ends in an inspectable artifact, so progress is measured by usable data and demonstrated operations.`, 'Proposed schedule for Task IV, start date specified in task document');
}
// IV.4
{
 const s=newSlide('Task IV · 4 / 5','Success means recovering the historical evidence','Evaluate on complete pages and matched units, then measure the cost of correction.');
 const rows=[['Regions + roles','Find full units, preserve streams','Region F1 ≥ .90; role macro-F1 ≥ .95'],['OCR + anchors','Recover the fields comparisons depend on','Names / citations exact recovery ≥ 95%'],['Linking + variants','Attach and group the correct paratexts','Locus linking F1 ≥ .95; grouping F1 ≥ .90'],['Substantive events','Detect attribution and qualification changes','Precision ≥ 95%; recall ≥ 90%'],['Historian effort','Reduce the work needed per usable unit','Median correction time at least halved']];
 rows.forEach((r,i)=>{const y=2.61+i*.68;rect(s,.74,y,11.86,.57,i%2?C.pale:C.white);text(s,r[0],.91,y+.12,2.51,.32,17,C.ink,true);text(s,r[1],3.66,y+.1,4.30,.37,14,C.muted);text(s,r[2],8.34,y+.09,4.05,.39,13,C.teal,true);});
 text(s,'Pilot targets · report by edition, typeface and class · score all 60 sealed test pages',.84,6.49,11.69,.39,16,C.muted);
 notes(s,`I would measure success at the points where errors affect the research. The pilot targets are region F1 of at least point nine and role macro-F1 of at least point nine five. For OCR, the key test is recovery of the names and citations used in comparisons, with ninety-five percent exact recovery as the target. Legal-locus linking and variant grouping receive their own reference sets. Attribution and qualification events are judged for both precision and recall: we need to know which changes were invented and which were missed. Results are broken down by edition, typeface and class. Finally, I compare timed manual work with assisted correction of comparable units, targeting a reduction of at least half in median correction time.`, 'Proposed pilot acceptance targets, not current model results; sealed evaluation comprises 60 complete pages and focal comparison units');
}
// IV.5
{
 const s=newSlide('Task IV · 5 / 5','Publish a reusable corpus and an answerable question','The first study: when and where did named interpretation become anonymous?');
 card(s,'GitHub','Versioned code · run scripts · tests\nAnnotation guide · evaluation protocol',.76,2.6,5.72,1.30,C.teal);
 card(s,'Hugging Face / archival release','Model weights · permitted annotations\nDataset / model cards · versioned identifiers',6.85,2.6,5.72,1.30,C.plum);
 rect(s,.76,4.25,11.81,1.00,C.pale);text(s,'Keep rights at the item level',.96,4.41,4.52,.32,20,C.ink,true);text(s,'Library identifiers + IIIF links + retrieval scripts\nRedistribute images only under their recorded terms.',5.63,4.41,6.58,.56,16,C.ink);
 text(s,'Matched loci × editions × attribution events',.87,5.74,11.57,.62,29,C.teal,true);
 text(s,'A corpus-wide pattern, with every conclusion linked back to its witnesses.',.88,6.49,11.69,.38,18,C.muted);
 notes(s,`The release separates code, models, annotations and library images. GitHub carries the implementation, launch scripts, annotation guide and evaluation protocol. A versioned model and dataset release carries weights and the annotations we can distribute. Every item retains its library identifier, source address and terms. Retrieval scripts reproduce image acquisition; image redistribution follows the recorded terms of each holding institution. The first historical output is a matched-locus study of attribution: which names survive, disappear or move between paratextual layers across the pilot editions. Scaling that design reveals patterns that individual reading cannot assemble systematically. The deliverable is therefore both a reusable research instrument and a concrete investigation, with each computational result linked back to the witnesses.`, 'Task IV publication requirement; source rights metadata in corpus/benchmark_inventory.json; proposed historical study');
}
// APPENDIX A — exact task access routes.
{
 const s=newSlide('Appendix · running the task','The committee can reproduce the result locally','See the package README for the supplied Windows launchers.');
 text(s,'Minimal task',.76,2.57,5.6,.42,24,C.teal,true);text(s,'python -m pip install opencv-python numpy\npython task1.py',.79,3.29,11.7,.91,21,C.ink,false,{fontFace:'Consolas'});
 text(s,'MDZ interfaces',.76,4.67,5.6,.42,24,C.teal,true);
 text(s,'IIIF image API: api.digitale-sammlungen.de/iiif/image/v2/bsb10144443_00040\nhOCR: api.digitale-sammlungen.de/ocr/bsb10144443/40\nImage: use 00041. OCR: use /41 for the second task page.',.8,5.36,11.70,1.15,17,C.ink);
 notes(s,'Backup slide for reproducibility questions. Use the submission README and supplied launchers. The minimal task uses only OpenCV and NumPy; Python standard-library modules provide the HTTP, parsing and CSV operations. The learned pipeline is supplied separately with its trained model assets.','task1_min/task1.py; final submission README',0);
}
// APPENDIX B
{
 const s=newSlide('Appendix · neural model evaluation','Neural v3: the complete confusion matrix','20 evaluation pages · reference in rows, prediction in columns');
 const names=['Text','Summarium','Inscriptio','Other','Outside'];names.forEach((n,i)=>text(s,n,3.83+i*1.60,2.68,1.51,.40,15,C.teal,true,{align:'center'}));
 names.forEach((n,i)=>{text(s,n,1.44,3.39+i*.55,2.17,.34,17,C.ink,true);names.forEach((_,j)=>{rect(s,3.83+j*1.60,3.29+i*.55,1.51,.47,i===j?C.teal:metrics.v3_confusion[i][j]>0?'E9D3CC':C.white);text(s,String(metrics.v3_confusion[i][j]),3.83+j*1.60,3.39+i*.55,1.51,.27,18,i===j?C.white:C.ink,i===j,{align:'center'});});});
 text(s,'Correct: 5,051 / 5,065 · Four-role macro-F1: 0.9450',1.48,6.49,10.49,.4,22,C.teal,true);
 notes(s,'Exact confusion matrix from the selected v3 training result. The supplied 384 region candidates are classified correctly. The role score is computed on supplied D-FINE/PERO lines, including outside lines. Four-role macro-F1 excludes outside from the average.','line_nn_v3/work/result_train_full.json; train_full.log',0);
}
// APPENDIX C
{
 const s=newSlide('Appendix · model and data specification','The shipped models and evaluation sets','Distinct stages have distinct datasets and outputs.');
 card(s,'D-FINE Large · epoch 14 / step 1400','100 training pages from 20 books; 20 evaluation pages from 20 other books.\nOne text-region class; 1,280-pixel input; score threshold 0.50.',.76,2.6,11.82,1.09);
 card(s,'PERO ParseNet_296000 + OCR_350000','Line detection and recognition run inside the D-FINE regions.\nLanguage-model decoding is switched off.',.76,3.98,11.82,1.09,C.plum);
 card(s,'Neural v3 · full.pt','100 training + 20 evaluation pages from ten Roman-glossed books.\nColour image + raw characters + coordinates + transformer page context.',.76,5.36,11.82,1.09,C.gold);
 notes(s,'D-FINE checkpoint: out/dfine_region_training_v1/full/best_instances.safetensors. Neural v3 checkpoint: line_nn_v3/models/full.pt. D-FINE training used the twenty-page evaluation set to select the checkpoint; v3 training used its own twenty-page evaluation set to select region and line weights. The printed task result uses the separate minimal rule program.','out/dfine_region_training_v1/data_manifest.json; line_nn_v3/model.py; line_nn_v3/work/train_full.log; out/dfine_pero_interview_v1/provenance.json',0);
}
async function main(){
 await pptx.writeFile({fileName:path.join(__dirname,'PetrIUS_Interview_15min.pptx')});
 let md='# PetrIUS interview — 15-minute speaker script\n\nConrad Compagna · Prepared 7 October 2026 · Interview 20 October 2026\n\nThree separate five-minute presentations. Slides 1–5: Task I; slides 6–10: Task III; slides 11–15: Task IV. Each slide has a 60-second speaking allocation, including a short pause to point to its visual. Appendix slides are for questions and do not enter the 15 minutes.\n\n';
 script.forEach(x=>{const st=(x.slide-1)*60;md+=`## ${String(Math.floor(st/60)).padStart(2,'0')}:00–${String(Math.floor((st+60)/60)).padStart(2,'0')}:00 · ${x.task} · Slide ${x.slide}\n\n**${x.title}**\n\n${x.body}\n\n`;});
 fs.writeFileSync(path.join(__dirname,'SPEAKER_SCRIPT.md'),md);fs.writeFileSync(path.join(__dirname,'slide_manifest.json'),JSON.stringify(script,null,2));
 console.log('Wrote PPTX, script, slide manifest. Main slides:15; appendix:3; timing:900sec.');
}
main();

