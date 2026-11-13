/**
 * @typedef {{
 *   string: string, number: number, boolean: boolean,
 *   object: object, array: any[], element: HTMLElement,
 *   function: Function
 * }} TypeMap
 *
 * @typedef {{status: "failed", data: {msg: string}}} CheckFail
 */

/**
 * @template {readonly {var: string, type: keyof TypeMap, def?: any, req?: boolean}[]} const C
 * @param {{input?: Object<string, any>, context: C}} arg
 * @returns {CheckFail | {
 *   status: "success",
 *   data: { msg: string, normal: { [K in C[number] as K["var"]]: TypeMap[K["type"]] } }
 * }}
 */

export function checkArg(arg){
let out = {status:"", data:{}}
let err = (r)=>{out["status"] = "failed";out["data"]["msg"] = r;return out};
let suc = (r,d)=>{out["status"] = "success";out["data"]["msg"] = r;out["data"]["normal"] = d;return out};

if(typeof arg != "object"){return err("[checkArg] function argument not object")}
if(!("input" in arg && "context" in arg)){return err("[checkArg] input or context not in argument")}
if(!(Array.isArray(arg["context"]))){return err("[checkArg] context not an array")}

let input = (typeof arg["input"]=="object") ? {...arg["input"]} : {};
let context = arg["context"];

for(let i=0; i<context.length; i++){
	let v = context[i];
	if(typeof v!="object"){return err("[checkArg] value include context is not a object")}
	if(!("var" in v && "type" in v)){return err("[checkArg] value include context is not complete")}
	
	v["type"] = v["type"].toLowerCase();
	v["req"] = "req" in v ? Boolean(v["req"]) : false;
	if(typeof input[v["var"]]!=v["type"]&&v["type"]!="array"&&v["type"]!="element"&&!(typeof input[v["var"]]=="undefined"&&!(v["req"]))){
		return err(`"${v["var"]}" is wrong type (require ${v["type"]} but received ${typeof input[v["var"]]})`)
	}
	if(!(Array.isArray(input[v["var"]]))&&v["type"]=="array"&&!(typeof input[v["var"]]=="undefined"&&!(v["req"]))){
		return err(`"${v["var"]}" is wrong type (require ${v["type"]} but received ${typeof input[v["var"]]})`)
	}
	if(!(input[v["var"]]?.nodeType==Node.ELEMENT_NODE)&&v["type"]=="element"&&!(typeof input[v["var"]]=="undefined"&&!(v["req"]))){
		return err(`"${v["var"]}" is wrong type (require ${v["type"]} but received ${typeof input[v["var"]]})`)
	}
	if(v["req"]){
		if(!(v["var"] in input)){
			return err(`"${v["var"]}" is require`)
		}
		if(v["type"]=="array"&&!(input[v["var"]].length>0)){
			return err(`"${v["var"]}" is require but received empty array`)
		}
		if(v["type"]=="object"&&Object.keys(input[v["var"]]).length==0){
			return err(`"${v["var"]}" is require but received empty object`)
		}
		if(v["type"]=="string"&&input[v["var"]]==""){
			return err(`"${v["var"]}" is require but received empty string`)
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
		if(v["type"]=="object"){
			if(typeof v["def"] == "object"){input[v["var"]]=v["def"]}
			else{input[v["var"]] = {}}
		}
		if(v["type"]=="element"){
			if(v["def"]?.nodeType == Node.ELEMENT_NODE){input[v["var"]]=v["def"]}
			else{input[v["var"]] = document.createElement("div")}
		}
		if(v["type"]=="function"){
			if(typeof v["def"] == "function"){input[v["var"]]=v["def"]}
			else{input[v["var"]] = ()=>{}}
		}
	}
}
return suc("[checkArg] sucess",input)
}