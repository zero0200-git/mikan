/**
 * @param {{container: HTMLElement, settingsList: {id: string, name: string, value: string, possible: string}[]}} arg
 * @returns {void}
 */
export async function displaySettings(arg) {
const { checkArg } = await import('./checkarg.js');
let check = checkArg({input:arg,context:[
	{
		type:"element",
		var:"container",
		req:true,
	},
	{
		type:"object",
		var:"settingsList",
		req:true,
	}
]});
if(check["status"]=="failed"){
	throw new Error(check["data"]["msg"]);
}
const container = check["data"]["normal"]["container"];
const settings = check["data"]["normal"]["settingsList"];

container.innerHTML = "";
container.dataset.displayType = "settings";
container.style = ""

settings.forEach(s=>{
	let id = s.id;
	let name = s.name;
	let value = s.value;
	let possible = s.possible;
	
	let div = document.createElement("div");
	div.dataset.id = id;
	div.dataset.name = name;

	let nameDiv = document.createElement("div");
	nameDiv.innerHTML = name;
	nameDiv.dataset.name = "";
	div.append(nameDiv);

	if(possible){
		let select = document.createElement("select");
		let choice = possible.split(",");
		select.dataset.input = "";
		choice.forEach(p=>{
			let option = document.createElement("option");
			option.value = p;
			option.innerHTML = p;
			select.append(option);
		})
		select.addEventListener("change",(e)=>{
			e.target.parentNode.dataset.value = e.target.value;
		})
		select.value = value;
		div.dataset.value = value;
		div.append(select);
	}else{
		let input = document.createElement("input");
		input.dataset.input = "";
		input.addEventListener("change",(e)=>{
			e.target.parentNode.dataset.value = e.target.value;
		})
		input.value = value;
		div.dataset.value = value;
		div.append(input);
	}
	container.append(div);
})

let footer = document.createElement("div");
footer.textContent = "Save Settings ";
let save = document.createElement("button");
save.addEventListener("click",async()=>{
	let settingsList = [];
	container.childNodes.forEach(s => {
		if(s.dataset.id === undefined){return}
		if(s.dataset.value === undefined){return}
		settingsList.push({id:s.dataset.id,value:s.dataset.value});
	});
	await saveSettings({settingsList});
});
save.innerHTML = "Save";
footer.append(save);
container.append(footer);

const { updateContentBar } = await import('./utils.js');
await updateContentBar({
	searchEnable: true,
	searchLink: (e)=>{
		container.childNodes.forEach(s=>{
			const id = s.dataset.id;
			const name = s.dataset.name;
			const re = new RegExp(e, "i");
			if(id?.search(re)<0 && name?.search(re)<0){
				s.style.display = "none"
			} else{
				s.style.display = ""
			}
		})
	},
	sortEnable: false,
	filterEnable: false,
})
}

/**
 * @param {{settingsList: {id:string,value:string}}[]} arg
 * @returns {Promise<void>}
 */
async function saveSettings(arg){
const { checkArg } = await import('./checkarg.js');
let check = checkArg({input:arg,context:[
	{
		type:"array",
		var:"settingsList",
		req:true,
	}
]});
if(check["status"]=="failed"){
	throw new Error(check["data"]["msg"]);
}
const settingsList = check["data"]["normal"]["settingsList"]
let checkSettingStuct = true;
let checkSettingStuctReason = "";
settingsList.every(s=>{
	const k = Object.keys(s)
	if(k.length != 2){
		checkSettingStuct = false;
		checkSettingStuctReason = k.length+" keys found. 2 keys required.";
		return false
	}
	if(!k.includes("id") || !k.includes("value")){
		checkSettingStuct = false;
		checkSettingStuctReason = "Keys must be id and value.";
		return false
	}
	if(s["id"]==""){
		checkSettingStuct = false;
		checkSettingStuctReason = "id is empty.";
		return false
	}
	if(s["id"]===undefined || s["value"]===undefined){
		checkSettingStuct = false;
		checkSettingStuctReason = "id and/or value is undefined.";
		return false
	}
})
if(checkSettingStuct){
	const { fetchApiData } = await import('./utils.js');
	await fetchApiData({type:"setsettings",valueObj:{type:"setsettings",value:JSON.stringify(settingsList)}});
}else{
	throw new Error("Settings structure incorrect. "+checkSettingStuctReason);
}
}