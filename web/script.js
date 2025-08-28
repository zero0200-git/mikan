async function login(arg){
let checkInput = checkArg({
	input:arg,
	context:[
		{
			var:"username",
			type:"string",
			req:true
		},
		{
			var:"password",
			type:"string",
			req:true
		}
	]
});
if(checkInput["status"]=="failed"){
	mikan.login=false;
	log('Login failed. '+checkInput["data"]["msg"]);
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];

const params = new URLSearchParams();
params.append('username', arg["username"]);
params.append('password', arg["password"]);

const response = await fetch(mikan["server"]+'/api/login', {
	method: 'POST',
	headers: {
		'Content-Type': 'application/x-www-form-urlencoded'
	},
	body: params.toString()
});

if (response.status === 200) {
	const data = await response.json();
	mikan["token"] = data.token;
	localStorage.setItem("token",JSON.stringify(mikan["token"]));
	mikan.login=true;
	log('Login successful');
	checkPage();
} else {
	mikan.login=false;
	log('Login failed');
}
}
async function fetchApiData(arg) {
let checkInput = checkArg({
	input:arg,
	context:[
		{
			var:"type",
			type:"string",
			req:true
		},
		{
			var:"value",
			type:"string"
		},
		{
			var:"valueObj",
			type:"object"
		}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];

let response;
if(Object.keys(arg["valueObj"]).length > 0){
let api = new URL(mikan["server"]+"/api");
api.search = new URLSearchParams(arg["valueObj"]);
a = api;
response = await fetch(api, {
	headers: {
		'Authorization': `Bearer ${mikan["token"]}`
	}
});
}
else{
response = await fetch(mikan["server"]+`/api?type=${arg["type"]}&value=${encodeURIComponent(arg["value"])}`, {
	headers: {
		'Authorization': `Bearer ${mikan["token"]}`
	}
});
}

if (response.status===200) {
	mikan.login=false;
	let data;
	try {
		data=(await response.json())
	} catch {
		data=(response.body)
	}
	return data;
} else if (response.status === 401) {
	mikan.login=false;
	log('Authorization failed');
	return ;
} else {
	log('Connection failed');
	return ;
}
}
async function serverEvent() {
	let retryCount = 0;
	let waitTime = 1000;
	const maxWaitTime = 30000;

	async function connect() {
		try {
			const response = await fetch(mikan["server"]+`/api/log`, {
				headers: {
					'Authorization': `Bearer ${mikan["token"]}`,
					"Accept": "text/event-stream",
					"Cache-Control": "no-cache",
					"Connection": "keep-alive"
				}
			});

			if (response.status === 200) {
				log('Connected to server log');
				retryCount = 0;
				waitTime = 1000;

				const reader = response.body.getReader();
				const decoder = new TextDecoder();
				let buffer = "";

				while (true) {
					const { value, done } = await reader.read();
					if (done) {
						log('Server connection closed');
						throw new Error('Connection closed');
					}
					
					buffer += decoder.decode(value, { stream: true });
					const lines = buffer.split('\n\n');
					buffer = lines.pop() || '';

					for(let line of lines) {
						if(line.trim().length > 0) {
							try {
								const match = line.match(/^data: (.+)$/m);
								if (match) {
									const data = JSON.parse(match[1]);
									if(data["type"] == "text") {
										log("["+data["timestamp"]+" server time] "+data["data"]);
									}
									else if(data["type"] == "progress") {
										mikan.progress = JSON.parse(data["data"]);
										if(history.state != null && history.state.page == "progress") {
											showProgress();
										}
									}
									else {
										log(data);
									}
								}
							} catch(e) {
								log(`Error parsing message: ${e.message}`);
							}
						}
					}
				}
			} else if (response.status === 401) {
				log('Authorization failed');
				mikan.login = false;
				throw new Error('Authorization failed');
			} else {
				throw new Error('Connection failed');
			}

		} catch(error) {
			log(`Error in server connection: ${error.message}`);
			log('Reconnecting in ' + (waitTime/1000) + 's...');
			
			retryCount++;
			waitTime = Math.min(waitTime * 1.5, maxWaitTime);
			
			await new Promise(resolve => setTimeout(resolve, waitTime));
			await connect();
		}
	}

	await connect();
}

function loadToken() {
let t=JSON.parse(localStorage.getItem("token"));
if(t!=null&&t!=undefined&&t!=""){mikan["token"]=t}
}
async function checkPage(){
let query = new URLSearchParams(location.search);
if(query.has("page")&&query.has("value")){changePage({page:query.get("page"),value:query.get("value")})}
else if(query.has("page")){changePage({page:query.get("page")})}
}
async function changePage(arg){
let checkInput = checkArg({
	input:arg,
	context:[
		{
			var:"page",
			type:"string",
			req:true
		},
		{
			var:"value",
			type:"string"
		}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];

if(["knownseries","search","knowngroups"].includes(arg["page"])){
	if(arg["value"]!=""){
		if(arg["page"]=="knownseries"){loadSeries({value:arg["value"]})}
		if(arg["page"]=="search"){searchSeries({value:arg["value"]})}
		if(arg["page"]=="knowngroups"){loadGroups({value:arg["value"]})}
	}else{
		if(arg["page"]=="knownseries"){loadSeries()}
		if(arg["page"]=="search"){searchSeries()}
		if(arg["page"]=="knowngroups"){loadGroups()}
	}
}
else if(arg["page"]=="settings"){showSettings()}
else if(arg["page"]=="progress"){showProgress()}
}
async function formWindow(arg){
let def = {
	location: document.body,
	title: "title",
	title: "title",
	form: [
		{
			id: "input",
			type: "text",
			value: "",
			name: "",
			disable: false
		}
	]
};
let out = {status:"", data:{}};

let checkInput = checkArg({
	input:arg,
	context:[
		{
			var:"id",
			type:"string",
			type:"formWindow"
		},
		{
			var:"location",
			type:"object",
			def:(document.body)
		},
		{
			var:"title",
			type:"string"
		},
		{
			var:"form",
			type:"array",
			req:true
		}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];

document.querySelectorAll(".formContainer .form[data-id='"+arg["id"]+"'").forEach(e=>e.cancel());

const container = document.createElement("div");
const title = document.createElement("div");
const form = document.createElement("form");
const action = document.createElement("div");
const actionConfirm = document.createElement("button");
const actionCancel = document.createElement("button");

container.classList.add("formContainer");
title.classList.add("title");
form.classList.add("form");
action.classList.add("action");

form.append(title);
container.append(form);
action.append(actionConfirm,actionCancel);

form.dataset.id = arg["id"];
title.innerHTML = arg["title"];
actionConfirm.innerHTML = "Confirm";
actionConfirm.type = "submit";
actionCancel.innerHTML = "Cancel";

form.style.width="0";
form.style.padding="0";
form.style.border="none";
form.style.pointerEvents="none";

form.method = "dialog";
let formInput = [];
for(let i of arg["form"]){
	const k = Object.keys(i);
	let input = document.createElement("input");
	const inputLabel = document.createElement("label");
	input.type = i["type"];
	input.dataset.id = i["id"];
	if(k.includes("name")){inputLabel.innerHTML = i["name"]+": "}
	if(k.includes("disable")){input.disabled = i["disable"]}
	if(k.includes("value")){input.value = i["value"]}
	if(k.includes("value")&&i["type"]=="checkbox"){input.checked = Boolean(i["value"])}
	if(k.includes("value")&&i["type"]=="select"){
		input = document.createElement("select");
		input.dataset.id = i["id"];
		const option = i["value"].split(",");
		for (let o=0; o<option.length;o++) {
			const selectOption = document.createElement("option");
			selectOption.value = option[o];
			selectOption.innerHTML = option[o];
			input.append(selectOption);
		}
	}
	inputLabel.append(input);
	form.append(inputLabel);
	formInput.push(input);
}
form.append(action);

setTimeout(()=>{
form.style.width="";
form.style.padding="";
form.style.border="";
form.style.pointerEvents="";
},40);

container.classList.add("center");
document.body.append(container);

container.style.opacity = "1";

return new Promise((resolve) => {
	form.addEventListener("submit", () => {
		out["status"] = "success";
		for (let i of formInput){
			out["data"][i.dataset.id] = i.value;
			if(i.type=="checkbox"){out["data"][i.dataset.id] = i.checked.toString()}
		}
		resolve(out);
		container.classList.add("remove");
		setTimeout(()=>{container.remove()},400);
	});
	actionConfirm.addEventListener("click", () => {
		out["status"] = "success";
		for (let i of formInput){
			out["data"][i.dataset.id] = i.value;
			if(i.type=="checkbox"){out["data"][i.dataset.id] = i.checked.toString()}
		}
		resolve(out);
		container.classList.add("remove");
		setTimeout(()=>{container.remove()},400);
	});
	actionCancel.addEventListener("click", () => {
		out["status"] = "failed";
		for (let i of formInput){
			out["data"][i.dataset.id] = i.value;
			if(i.type=="checkbox"){out["data"][i.dataset.id] = i.checked.toString()}
		}
		resolve(out);
		container.classList.add("remove");
		setTimeout(()=>{container.remove()},400);
	});
	form.cancel = () => {
		out["status"] = "failed";
		for (let i of formInput){
			out["data"][i.dataset.id] = i.value;
			if(i.type=="checkbox"){out["data"][i.dataset.id] = i.checked.toString()}
		}
		resolve(out);
		container.classList.add("remove");
		setTimeout(()=>{container.remove()},400);
	};
});
}
async function displayTable(arg){
let checkInput = checkArg({
	input:arg,
	context:[
		{
			var:"data",
			type:"object",
			req:true
		},
		{
			var:"link",
			type:"boolean",
			def:false
		},
		{
			var:"action",
			type:"object"
		}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];

if(arg.data.length==0){return}
mikan.tableData = arg.data;
await sortTable();
const key = [];
const colsAll = Object.keys(arg.data[0]);
const cols = [];
const con = document.querySelector("#content");
for(let v of colsAll){
	if(v.includes("provider")){key.push(v);cols.push(v)}
	else if(v.includes("id")){key.push(v)}
	else if(v.includes("action")!=true){cols.push(v)}
}
con.innerHTML = "";
con.dataset.displayType = "table";
document.querySelector("#serieCover img").style.display="none";
document.querySelector("#serieCover img").src="";
document.querySelector("#serieCover").style.height="0";
document.body.style.removeProperty("--background");


let dataLen = []
let dataLenMax = (100/(cols.length-1))*.9;
let dataLenMin = 20;
let dataLenNormal = false;
for (const k of cols) {dataLen.push(arg.data[0][k].toString().length>dataLenMin?arg.data[0][k].toString().length:dataLenMin)}
function tableNormal(){
for (let i=0; (i<10)&&(dataLenNormal!=true); i++) {
let r = dataLen.reduce((sum,val)=>sum+val,0);
dataLen=dataLen.map(val => ((Math.ceil(((val/r)*100)))>dataLenMax?dataLenMax:(Math.ceil(((val/r)*100)))));
dataLenNormal = !(dataLen.some(n => n>50)||(dataLen.reduce((sum,val)=>sum+val,0))<98);
}
con.style.setProperty("--col-template", dataLen.slice(0,-1).map(n=>n.toFixed(2)+"%").join(" ")+" auto");
}
tableNormal();

const header = document.createElement("div");
header.classList.add("header");
con.append(header);
for (let i = 0; i < cols.length; i++) {
	const head = document.createElement("div");
	head.innerHTML = cols[i];
	head.dataset.head = cols[i];
	head.title = cols[i]+" (click to filter)";
	head.classList.add("header");
	head.tabIndex=0;
	head.addEventListener("click",async(e)=>{if(head.dataset["select"]!="true"){
		document.querySelectorAll("#content .header[data-select=true]").forEach(e=>{e.dataset["select"]="false"});
		head.dataset["select"]="true";
	}else if(head.dataset["select"]=="true"){
		e.preventDefault();
		head.dataset["select"]="false";
		let filter = await formWindow({title:"Filter: "+cols[i],form:[{id:"filter",type:"text"}]});
		if(filter["status"]=="success"){
			let el = document.querySelectorAll("#content > .data > *:nth-child("+cols.length+"n+"+(i+1)+"):not(.scrollbar)")
			let text = filter["data"]["filter"]
			let re = new RegExp(text,"i")
			for(let e = 0; e < el.length; e++) {
				let row = document.querySelectorAll("#content > .data > [data-row='"+el[e].dataset.row+"']");
				if(el[e].innerText.search(re)<0){
					row.forEach(e => {e.style.display="none"})
				}else{row.forEach(e => {e.style.display=""})}
			}
			document.querySelectorAll("#content > .header > .header").forEach(e=>{e.dataset["filter"]="";e.innerHTML=e.dataset.head;});
			if(filter["data"]["filter"]!=""){head.dataset.filter=text;head.innerHTML = cols[i]+' (filter: "'+text+'")'}else{head.innerHTML = cols[i]}
		}
		}});
	let cc = []
	for (let j=0; j<colsAll.length; j++) {
		for (const s of ["asc","desc"]){
			cc.push({
				id: "Sort by \""+colsAll[j]+"\" "+s,
				name: "Sort by \""+colsAll[j]+"\" "+s,
				value: "",
				action: ()=>{
					if(mikan.sortLast.includes(colsAll[j])){mikan.sortLast.splice(mikan.sortLast.indexOf(colsAll[j]),1)}
					mikan.sortLast.unshift(colsAll[j]);
					mikan.sort[colsAll[j]]=s;
					displayTable({data:arg.data,link:arg.link,action:arg.action});
				}
			});
		}
	}

	head.addEventListener("contextmenu", (e) => {contextMenu({id:"tableHeader",location:head,event:e,context:cc})});
	header.append(head);
}

const dataSec = document.createElement("div");
dataSec.classList.add("data");
con.append(dataSec);
dataLen = Array.from({length: cols.length},()=>0);
const dataLoad = new IntersectionObserver(entries => {
	entries.forEach(entry => {
		entry.target.style.visibility = entry.isIntersecting ? 'visible' : 'hidden';
	});
}, {
	root: dataSec,
	rootMargin: '100%',
	threshold: 0
});
for (let i=0; i<arg["data"].length; i++) {
	const url = new URL(location);
	for (let d = 0; d < cols.length; d++) {
		dataLen[d] = dataLen[d] + (arg["data"][i][cols[d]].toString().length>dataLenMin?arg["data"][i][cols[d]].toString().length:dataLenMin);
		dataLenNormal = false;
		const dataCol = arg.link ? document.createElement("a") : document.createElement("div");
		dataCol.append(arg["data"][i][cols[d]]=="" ? " " : arg["data"][i][cols[d]]);
		dataCol.title = arg["data"][i][cols[d]].innerText||arg["data"][i][cols[d]].value||arg["data"][i][cols[d]]||arg["data"][i][cols[d-1]];
		dataCol.dataset["row"] = i+1;
		dataCol.dataset["select"] = "false";
		dataCol.tabIndex=0;
		if(arg.link){
			url.searchParams.set("value", arg["data"][i][key[0]]);
			dataCol.addEventListener("click",()=>{if(dataCol.dataset["select"]=="true"){history.pushState({page:url.searchParams.get("page"),value:key[0]},"", url);checkPage()}})
		}

		for(const id of key){dataCol.dataset[id] = arg["data"][i][id]}
		dataCol.addEventListener("click",async()=>{if(dataCol.dataset["select"]!="true"){
			document.querySelectorAll("#content .data > *[data-select=true]").forEach(e=>{e.dataset["select"]="false"});
			document.querySelectorAll("#content .data > *[data-row='"+dataCol.dataset["row"]+"']").forEach(e=>{e.dataset["select"]="true"});
			if(typeof dataCol.dataset["serieid"]=="string"&&typeof dataCol.dataset["provider"]=="string"){
				document.querySelector("#serieCover img").style.display="";
				document.querySelector("#serieCover img").src="/api?type=getcover&provider="+dataCol.dataset["provider"]+"&id="+dataCol.dataset["serieid"];
				document.body.style.setProperty("--background", "url(/api?type=getcover&provider="+dataCol.dataset["provider"]+"&id="+dataCol.dataset["serieid"]+")");
				document.querySelector("#serieCover").style.height="";
			}else{
				document.querySelector("#serieCover img").style.display="none";
				document.querySelector("#serieCover img").src="";
				document.querySelector("#serieCover").style.height="0";
				document.body.style.removeProperty("--background");
			}
		}})

		let cc = []
		const acKey=Object.keys(arg["action"]);
		if(acKey.length>0){
		for (const ac of acKey) {
			cc.push({
				id: arg["action"][ac],
				name: arg["action"][ac],
				value: "",
				action: ()=>{
					if("serieid" in arg["data"][i]){tableAction({action:ac,value:arg["data"][i]["serieid"]})}
					else{tableAction({action:ac,value:arg["data"][i][key[0]]})}
				}
			});
		}
		}
		if("action" in arg["data"][i]){
		for (const ac of arg["data"][i]["action"]) {
			cc.push({
				id: ac["name"],
				name: ac["name"],
				value: "",
				action: ()=>ac["func"]()
			});
		}
		}
		if(acKey.length>0||"action" in arg["data"][i]){dataCol.addEventListener("contextmenu", (e) => {contextMenu({id:"tableDataRow"+(i+1),location:dataCol,event:e,context:cc})})}
		dataSec.append(dataCol);
		dataLoad.observe(dataCol);
	}
}
const dataScroll = document.createElement("div");
const dataScroller = document.createElement("div");
dataScroll.classList.add("scrollbar");
dataScroller.classList.add("scroller");
dataScroll.style.height = dataSec.offsetHeight+"px";
dataScroller.style.height = dataSec.scrollHeight+"px";
dataSec.addEventListener("resize",function(){
	dataScroll.style.height = dataSec.offsetHeight+"px";
	dataScroller.style.height = dataSec.scrollHeight+"px";
});
let scon = setTimeout(async()=>{dataScroll.style.opacity=""},400);
dataScroll.onscroll = async()=>{dataSec.onscroll="";dataSec.scrollTop=dataScroll.scrollTop}
dataScroll.onscrollend = async()=>{dataSec.onscroll = async()=>{dataScroll.onscroll="";clearTimeout(scon);dataScroll.style.opacity=1;dataScroll.scrollTop=dataSec.scrollTop;scon = setTimeout(async()=>{dataScroll.style.opacity=""},200);}}
dataSec.onscroll = async()=>{dataScroll.onscroll="";clearTimeout(scon);dataScroll.style.opacity=1;dataScroll.scrollTop=dataSec.scrollTop;scon = setTimeout(async()=>{dataScroll.style.opacity=""},200);}
dataSec.onscrollend = async()=>{dataScroll.onscroll = async()=>{dataSec.onscroll="";dataSec.scrollTop=dataScroll.scrollTop}}
dataScroll.append(dataScroller);
con.append(dataScroll);
tableNormal();
}
async function sortTable() {
const tsort = mikan.sort;
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

mikan.tableData.sort((a, b) => {
	for (const key of mikan.sortLast) {
		if (key in a && key in b) {
			const order = tsort[key];
			const comparison = collator.compare(a[key], b[key]);
			if (comparison !== 0) {
				return order === "asc" ? comparison : -comparison;
			}
		}
	}
	return 0;
})
}
async function loadSeries(arg){
let checkInput = checkArg({
	input:arg,
	context:[
		{
			var:"value",
			type:"string",
		}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];
if(arg["value"]!=""){
	
	mikan.tableData = (await fetchApiData({type:"knownserieschapter",value:arg["value"]}))["data"].map(e=>{e["action"]=[
		{
			name:"Download chapter",
			func:()=>{
				log("tableAction act:"+"dlchapter"+" val:"+e["chapterid"],true);
				fetchApiData({type:"dlchapter",valueObj:{type:"dlchapter",id:e["chapterid"],serie:e["serieid"]}})
			}
		},
	];return e});
	displayTable({data:mikan.tableData})
}else{
	mikan.tableData = (await fetchApiData({type:"knownseries"}))["data"].map(e=>{if("h" in e){e.h=Boolean(e.h).toString();return e}}).map(e=>{e["action"]=[
		{
			name:"Update to lastest chapter and download",
			func:()=>{
				log("tableAction act:"+"updateanddllast"+" val:"+e["serieid"],true);
				fetchApiData({type:"updateanddllast",valueObj:{type:"updateanddllast",provider:e["provider"],id:e["serieid"]}})
			}
		},
		{
			name:"Update to lastest chapter",
			func:()=>{
				log("tableAction act:"+"updatechapter"+" val:"+e["serieid"],true);
				fetchApiData({type:"updatechapter",valueObj:{type:"updatechapter",provider:e["provider"],id:e["serieid"]}})
			}
		},
		{
			name:"Download until lastest chapter",
			func:()=>{
				log("tableAction act:"+"dllast"+" val:"+e["serieid"],true);
				fetchApiData({type:"dllast",valueObj:{type:"dllast",provider:e["provider"],id:e["serieid"]}})
			}
		},
		{
			name:"Update serie info to lastest",
			func: ()=>{
				log("tableAction act:"+"updateserie"+" val:"+e["serieid"],true);
				fetchApiData({type:"updateserie",valueObj:{type:"updateserie",provider:e["provider"],id:e["serieid"]}})
			}
		},
		{
			name:"Update to lastest cover",
			func: ()=>{
				log("tableAction act:"+"updatecover"+" val:"+e["serieid"],true);
				fetchApiData({type:"updatecover",valueObj:{type:"updatecover",provider:e["provider"],id:e["serieid"]}})
			}
		},
	];return e});
	displayTable({data:mikan.tableData,link:true,action:{
		forceName:'Force save serie name',
		markH:'Mark H'
	}})
}
}
async function searchSeries(arg){
let checkInput = checkArg({
	input:arg,
	context:[
		{
			var:"value",
			type:"string",
		},
		{
			var:"provider",
			type:"string",
		}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];
if(arg["value"]==""){
	const searchValue = await formWindow({title:"Search",form:[{id:"value",name:"search",type:"text"},{id:"provider",name:"provider",type:"select",value:"mangadex,comick"}]});
	if(searchValue["status"]=="success"){
		searchValue["data"]["type"]="search";
		const url = new URL(location);
		url.searchParams.set("value", searchValue["data"]);
		history.pushState({page:"search",value:searchValue["data"]},"", url);
		const data = (await fetchApiData({type:"search",valueObj:searchValue["data"]}))["data"].map(e=>{e["action"]=[
			{
				name:"Add this manga",
				func: ()=>{
					log("tableAction act:"+"addserie"+" val:"+e["serieid"],true);
					fetchApiData({type:"addserie",valueObj:{type:"addserie",provider:e["provider"],id:e["serieid"]}})
				}
			}
		];return e});
		displayTable({data:data})
	}
}else if(arg["value"]!=""&&arg["provider"]!=""){
	const url = new URL(location);
	url.searchParams.set("value", arg["value"]);
	history.pushState({page:"search",value:arg["value"]},"", url)
	const data = (await fetchApiData({type:"search",valueObj:arg}))["data"];
	displayTable({data:data,action:{addSerie:"Add this manga"}})
}
}
async function loadGroups(arg){
let checkInput = checkArg({
	input:arg,
	context:[
		{
			var:"value",
			type:"string",
		}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];
if(arg["value"]!=""){
	mikan.tableData = (await fetchApiData({type:"knowngroups",value:arg["value"]}))["data"].map(e=>({tgroupid:e.tgroupid,name:e.name,ignore:Boolean(e.ignore).toString(),fake:Boolean(e.fake).toString(),deleted:Boolean(e.deleted).toString()}));
	displayTable({data:mikan.tableData,action:{markgroup:"Mark ignore/fake/deleted group data"}})
}else{
	mikan.tableData = (await fetchApiData({type:"knowngroups",value:arg["value"]}))["data"].map(e=>({tgroupid:e.tgroupid,name:e.name,ignore:Boolean(e.ignore).toString(),fake:Boolean(e.fake).toString(),deleted:Boolean(e.deleted).toString()}));
	displayTable({data:mikan.tableData,action:{markgroupignore:"Mark ignore group data",markgroupfake:"Mark fake group data",markgroupdeleted:"Mark deleted group data"}})
}
}
async function tableAction(arg){
let checkInput = checkArg({
	input:arg,
	context:[
		{
			var:"action",
			type:"string",
			req:true
		},
		{
			var:"value",
			type:"string",
			req:true
		}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];
log("tableAction act:"+arg["action"]+" val:"+arg["value"],true)
if(arg["action"]=="addSerie"){
if("serieid" in arg["value"] && "provider" in arg["value"]){
fetchApiData({type:"addserie",id:arg["value"]["serieid"],provider:arg["value"]["provider"]})
}
} else if(arg["action"]=="updateSerie"){
fetchApiData({type:"updateserie",value:arg["value"]})
} else if(arg["action"]=="dlLast"){
fetchApiData({type:"dllast",value:arg["value"]})
} else if(arg["action"]=="updatechapter"){
fetchApiData({type:"updatechapter",value:arg["value"]})
} else if(arg["action"]=="updateanddllast"){
fetchApiData({type:"updateanddllast",value:arg["value"]})
} else if(arg["action"]=="updateCover"){
fetchApiData({type:"updatecover",value:arg["value"]})
} else if(arg["action"]=="markH"){
const markValue = await formWindow({title:"H",form:[{id:"markh",type:"checkbox",value:mikan.tableData.find(e=>e.serieid==arg["value"]).h=="true"?true:false}]});
if(markValue["status"]=="success"){await fetchApiData({type:"markh",value:arg["value"]+"markh"+(markValue["data"]["markh"]=="true"?"1":"0")});checkPage()}
} else if(arg["action"]=="forceName"){
const info = await formWindow({title:"Force use name", form:[{id:"name",type:"text"}]})
if(info["status"]=="success"){fetchApiData({type:"updateforcename",value:JSON.stringify({id:arg["value"],name:info["data"]["name"]})})}
} else if(arg["action"]=="markgroupignore"){
const markValue = await formWindow({title:"Mark group ignore",form:[{id:"ignore",type:"checkbox",value:mikan.tableData.find(e=>e.tgroupid==arg["value"]).ignore=="true"?true:false}]});
if(markValue["status"]=="success"){await fetchApiData({type:"knowngroupsset",value:arg["value"]+"markignore"+(markValue["data"]["ignore"]=="true"?"1":"0")})}
checkPage()
} else if(arg["action"]=="markgroupfake"){
const markValue = await formWindow({title:"Mark group fake",form:[{id:"fake",type:"checkbox",value:mikan.tableData.find(e=>e.tgroupid==arg["value"]).fake=="true"?true:false}]});
if(markValue["status"]=="success"){await fetchApiData({type:"knowngroupsset",value:arg["value"]+"markfake"+(markValue["data"]["fake"]=="true"?"1":"0")})}
checkPage()
} else if(arg["action"]=="markgroupdeleted"){
const markValue = await formWindow({title:"Mark group deleted",form:[{id:"deleted",type:"checkbox",value:mikan.tableData.find(e=>e.tgroupid==arg["value"]).deleted=="true"?true:false}]});
if(markValue["status"]=="success"){await fetchApiData({type:"knowngroupsset",value:arg["value"]+"markdeleted"+(markValue["data"]["deleted"]=="true"?"1":"0")})}
checkPage()
}
}
async function log(value,trance=false){
if((trance==true&&mikan.debug==true)||trance==false){
const date = new Date();
const dateFormat = date.toISOString().slice(0, 10)+" "+date.toTimeString().slice(0,8);
value="["+dateFormat+"] "+value;
console.log(value);
const txt=document.createElement("p");
txt.innerHTML=value.toString();
const logEle=document.querySelector("#log>div:nth-child(2)");
const logEleChild=logEle.childNodes;
if(logEleChild.length>0){
logEle.insertBefore(txt,logEleChild[0]);
}else{
logEle.append(txt);
}
logEle.scrollTop = 0;
}
}
async function showSettings(){
let data = (await fetchApiData({type:"getsettings"}))["data"];
data.forEach(e=>{
	let v=e.value;
	e.value=document.createElement("input");
	e.value.value=v;
})
let save=document.createElement("button");
save.addEventListener("click",saveSettings);
save.innerHTML="Save";
data.push({id:"saveSetting",name:"Save Settings",value:save});
displayTable({data:data})
}
async function saveSettings(){
const url = new URL(location);
if("settings"==url.searchParams.get("page")){
	let list=document.querySelectorAll("#content [data-id]:not([data-id=saveSetting]) input");
	let data=[];
	for (let i = 0; i < list.length; i++){
		data.push({id:list[i].parentNode.dataset.id,value:list[i].value})
	}
	fetchApiData({type:"setsettings",value:JSON.stringify(data)});
	log("save settings: "+JSON.stringify(data),true)
}
}
async function showProgress(){
let data = [];
let progress = mikan.progress;
Object.keys(progress).forEach(e=>{
	let ptmp = progress[e];
	ptmp["serieid"]=e;
	const progressCol = ["progress","subprogress"];
	progressCol.forEach(pro=>{
		const pCon = document.createElement("div");
		const p = document.createElement("div");
		pCon.classList.add("progressCon");
		p.classList.add("progress");
		let t;
		try{t = ptmp[pro].innerText!=undefined ? ptmp[pro].innerText : ptmp[pro]+"%"}
		catch{ptmp[pro]+"%"}
		p.style.width = t;
		p.innerHTML = t;
		pCon.append(p);
		ptmp[pro] = pCon;
	})
	data.push(ptmp);
})
displayTable({data:data})
}
async function contextMenu(arg){
let def = {
	id: "",
	title: "",
	location: document.body,
	x:0,
	y:0,
	event:{},
	context: [
		{
			id: "input",
			name: "text",
			value: "",
			action: ()=>{}
		}
	]
};
let out = {status:"", data:{}}
let checkInput = checkArg({
	input:arg,
	context:[
		{
			var:"id",
			type:"string",
			def:"context"
		},
		{
			var:"title",
			type:"string",
		},
		{
			var:"location",
			type:"object",
			def:document.body
		},
		{
			var:"x",
			type:"number"
		},
		{
			var:"y",
			type:"number"
		},
		{
			var:"event",
			type:"object"
		},
		{
			var:"context",
			type:"array"
		}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];
const body = document.body;
const con = document.querySelector("#context");
const all = con.querySelectorAll("*");
const oldId = con.querySelectorAll("[data-context-id='"+arg["id"]+"']")
if(oldId.length>0){oldId.forEach(e=>con.removeChild(e));return}
arg["event"].preventDefault();
try{all.forEach(e=>e.rm())}catch{}

const contextCon = document.createElement("div");
contextCon.classList.add("context");
contextCon.tabIndex=0;
contextCon.dataset.contextId = arg["id"];
let relocation = ()=>{
contextCon.style.top = (arg["location"].getBoundingClientRect().y+arg["y"])+"px";
contextCon.style.left = (arg["location"].getBoundingClientRect().x+arg["x"])+"px";
contextCon.style.maxHeight = (body.offsetHeight-(arg["location"].getBoundingClientRect().y+arg["y"]))+"px";
contextCon.style.maxWidth = (body.offsetWidth-(arg["location"].getBoundingClientRect().x+arg["x"]))+"px";
};
if(arg["event"]!={}){
const yPerc = arg["event"].offsetY/arg["location"].scrollHeight;
const xPerc = arg["event"].offsetX/arg["location"].scrollWidth;
relocation = ()=>{
contextCon.style.top = ((yPerc*arg["location"].scrollHeight)+arg["location"].getBoundingClientRect().y+arg["y"]+8)+"px";
contextCon.style.left = ((xPerc*arg["location"].scrollWidth)+arg["location"].getBoundingClientRect().x+arg["x"]+8)+"px";
contextCon.style.maxHeight = (body.offsetHeight-((yPerc*arg["location"].scrollHeight)+arg["location"].getBoundingClientRect().y+arg["y"]))+"px";
contextCon.style.maxWidth = (body.offsetWidth-((xPerc*arg["location"].scrollWidth)+arg["location"].getBoundingClientRect().x+arg["x"]))+"px";
};
}

relocation();
window.addEventListener("resize",relocation);
con.append(contextCon);

let parentSc = (el)=>{
	if(el!=body){
		el.parentNode.addEventListener("scroll",relocation);
		if(el.parentNode!=body){parentSc(el.parentNode)}
	}
}
let parentScRm = (el)=>{
	if(el!=body){
		el.parentNode.removeEventListener("scroll",relocation);
		if(el.parentNode!=body){parentScRm(el.parentNode)}
	}
}
parentSc(arg["location"]);

const reEvt = () => {
con.removeChild(contextCon);
window.removeEventListener("resize",relocation);
contextCon.removeEventListener("mouseleave",reEvt);
parentScRm(arg["location"]);
}
contextCon.rm = reEvt;

for(let c=0; c<arg["context"].length; c++) {
const context = document.createElement("button");
context.innerHTML = arg["context"][c]["name"];
context.tabIndex = 1;
context.addEventListener("click",()=>{reEvt();arg["context"][c]["action"]()});
context.addEventListener("mouseenter",context.focus);
contextCon.append(context);
}
const contextClose = document.createElement("button");
contextClose.innerHTML = "Close menu";
contextClose.tabIndex = 1;
contextClose.addEventListener("click",reEvt);
contextClose.addEventListener("mouseenter",contextClose.focus);
contextCon.append(contextClose);

contextCon.querySelector("*").focus();
contextCon.addEventListener("mouseleave",reEvt);
}
function checkArg(arg){
let data = {
	input: {},
	context: [
		{
			var: "text",
			type: "string",
			def: "default",
			req: false
		}
	]
}
let out = {status:"", data:{}}
let err = (r)=>{out["status"] = "failed";out["data"]["msg"] = r;return out};
let suc = (r,d)=>{out["status"] = "success";out["data"]["msg"] = r;out["data"]["normal"] = d;return out};

if(typeof arg != "object"){return err("[checkArg] function argument not object")}
if(!("input" in arg && "context" in arg)){return err("[checkArg] input or context not in argument")}
if(!(Array.isArray(arg["context"]))){return err("[checkArg] context not an array")}
if(typeof arg["input"]!="object"){arg["input"]={}}

let input = arg["input"];
let context = arg["context"];

for(let i=0; i<context.length; i++){
	let v = context[i];
	if(typeof v!="object"){return err("[checkArg] value include context is not a object")}
	if(!("var" in v && "type" in v)){return err("[checkArg] value include context is not complete")}
	
	v["type"] = v["type"].toLowerCase();
	v["req"] = "req" in v ? Boolean(v["req"]) : false;
	if(typeof input[v["var"]]!=v["type"]&&v["type"]!="array"&&!(typeof input[v["var"]]=="undefined"&&!(v["req"]))){
		return err(`"${v["var"]}" is wrong type (require ${v["type"]} but received ${typeof input[v["var"]]})`)
	}
	if(!(Array.isArray(input[v["var"]]))&&v["type"]=="array"&&!(typeof input[v["var"]]=="undefined"&&!(v["req"]))){
		return err(`"${v["var"]}" is wrong type (require ${v["type"]} but received ${typeof input[v["var"]]})`)
	}
	if(v["req"]){
		if(!(v["var"] in input)){
			return err(`"${v["var"]}" is require`)
		}
		if(v["type"]=="array"&&!(input[v["var"]].length>0)){
			return err(`"${v["var"]}" is require but received emply array`)
		}
		if(v["type"]=="object"&&Object.keys(input[v["var"]]).length<0){
			return err(`"${v["var"]}" is require but received emply object`)
		}
		if(v["type"]=="string"&&input[v["var"]]==""){
			return err(`"${v["var"]}" is require but received emply string`)
		}
		if(v["type"]=="number"&&isNaN(input[v["var"]])){
			return err(`"${v["var"]}" is require but received NaN (Not a Number)`)
		}
	}
	if(typeof input[v["var"]]=="undefined"){
		if(v["type"]=="array"){
			if(Array.isArray(v["def"])){input[v["var"]]=v["def"]}
			else{input[v["var"]] = []}
		}
		if(v["type"]=="object"){
			if(typeof v["def"] == "object"){input[v["var"]]=v["def"]}
			else{input[v["var"]] = {}}
		}
		if(v["type"]=="string"){
			if(typeof v["def"] == "string"){input[v["var"]]=v["def"]}
			else{input[v["var"]] = ""}
		}
		if(v["type"]=="number"){
			if(typeof v["def"] == "number"){input[v["var"]]=v["def"]}
			else{input[v["var"]] = 0}
		}
		if(v["type"]=="boolean"){
			if(typeof v["def"] == "boolean"){input[v["var"]]=v["def"]}
			else{input[v["var"]] = false}
		}
	}
}
return suc("[checkArg] sucess",input)
}



mikan={};
mikan.sort={name:"asc"};
mikan.sortLast=["name"];
mikan.progress={};
mikan.login=false;
mikan.debug=false;
mikan.server=window.location.origin;
let load1st=()=>{
	loadToken()
	checkPage()
	serverEvent()
}
let checklogin1st = async() => {
	try{
		if(localStorage.getItem("token")!=null) {
			let r = await fetch(mikan["server"]+'/api?type=ping', {
			headers: {'Authorization': `Bearer ${JSON.parse(localStorage.getItem("token"))}`}
			});
			if(r.status == 200){mikan.login = true; load1st()}
			else{log("Login token not valid, Please try login again."); document.querySelector("#login").click()}
			
		}
	}catch{
		log("Login token corrupt, Please try login again.")
		document.querySelector("#login").click();
	}
};

document.querySelector("#app > header > button:nth-child(1)").addEventListener("click", () => {
	const nav = document.querySelector("#container > nav");
	nav.style.width = nav.style.width === '' ? '0' : '';
	nav.style.padding = nav.style.padding === '' ? '0' : '';
	nav.style.margin = nav.style.margin === '' ? '0' : '';
	nav.style.visibility = nav.style.visibility === '' ? 'hidden' : '';
});
document.querySelectorAll("nav>button").forEach(n => {if(n.id!="log"){
	const url = new URL(location);
	url.searchParams.set("page", n.value);
	url.searchParams.set("value", "");
	n.addEventListener("click",()=>{history.pushState({page:n.value,value:""}, "", url);checkPage()})
}});
document.querySelector("#login").addEventListener('click', async () => {
	const info = await formWindow({title:"Login", form:[{id:"username",type:"text",name:"username"},{id:"password",type:"password",name:"password"}]})
	if(info["status"]=="success"){
		login({username:info["data"]["username"],password:info["data"]["password"]},)
	}
});
window.addEventListener('popstate', checkPage);
log("script loaded");
checklogin1st();