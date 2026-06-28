export const MODULE_JOB_SCHEMAS = [
  ["proced.xsd", "proced.xsd"],
  ["process.xsd", "process.xsd"],
  ["descript.xsd", "descript.xsd"],
  ["schedul.xsd", "schedul.xsd"],
  ["container.xsd", "container.xsd"],
  ["crew.xsd", "crew.xsd"],
];

const MODULE_JOB_CONFIG = {
  pack_modules: {
    title: "Pack modules",
    submitLabel: "Pack",
    defaultLabel: "pack modules",
  },
  unpack_modules: {
    title: "Unpack modules",
    submitLabel: "Unpack",
    defaultLabel: "unpack modules",
  },
};

const FILE_JOB_CONFIG = {
  convert_sap_to_bit_xml: {
    title: "ETK SAP to bitplant XML",
    submitLabel: "Convert",
    description: "Use paths relative to the imported version snapshot.",
  },
  convert_opmanual_to_bit_xml: {
    title: "Opmanual to bitplant XML",
    submitLabel: "Convert",
    description: "Enter one opmanual XML path per line, relative to the imported version snapshot.",
  },
};

export function getModuleJobConfig(kind) {
  return MODULE_JOB_CONFIG[kind] || null;
}

export function isModuleJob(kind) {
  return Boolean(getModuleJobConfig(kind));
}

export function getFileJobConfig(kind) {
  return FILE_JOB_CONFIG[kind] || null;
}

export function isFileJob(kind) {
  return Boolean(getFileJobConfig(kind));
}
