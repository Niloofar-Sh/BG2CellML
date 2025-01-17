from libcellml import Component, Generator, GeneratorProfile, Model, Units,  Variable, ImportSource, Printer, Annotator
import pandas as pd
from utilities import print_model, ask_for_file_or_folder, ask_for_input, infix_to_mathml
import sys
import cellml
from pathlib import PurePath 

MATH_HEADER = '<math xmlns="http://www.w3.org/1998/Math/MathML" xmlns:cellml="http://www.cellml.org/cellml/2.0#">\n'
MATH_FOOTER = '</math>\n'
BUILTIN_UNITS = {'ampere':Units.StandardUnit.AMPERE, 'becquerel':Units.StandardUnit.BECQUEREL, 'candela':Units.StandardUnit.CANDELA, 'coulomb':Units.StandardUnit.COULOMB, 'dimensionless':Units.StandardUnit.DIMENSIONLESS, 
                 'farad':Units.StandardUnit.FARAD, 'gram':Units.StandardUnit.GRAM, 'gray':Units.StandardUnit.GRAY, 'henry':Units.StandardUnit.HENRY, 'hertz':Units.StandardUnit.HERTZ, 'joule':Units.StandardUnit.JOULE,
                   'katal':Units.StandardUnit.KATAL, 'kelvin':Units.StandardUnit.KELVIN, 'kilogram':Units.StandardUnit.KILOGRAM, 'liter':Units.StandardUnit.LITRE, 'litre':Units.StandardUnit.LITRE, 
                   'lumen':Units.StandardUnit.LUMEN, 'lux':Units.StandardUnit.LUX, 'metre':Units.StandardUnit.METRE, 'meter':Units.StandardUnit.METRE, 'mole':Units.StandardUnit.MOLE, 'newton':Units.StandardUnit.NEWTON, 
                   'ohm':Units.StandardUnit.OHM, 'pascal':Units.StandardUnit.PASCAL, 'radian':Units.StandardUnit.RADIAN, 'second':Units.StandardUnit.SECOND, 'siemens':Units.StandardUnit.SIEMENS, 'sievert':Units.StandardUnit.SIEVERT, 
                   'steradian':Units.StandardUnit.STERADIAN, 'tesla':Units.StandardUnit.TESLA, 'volt':Units.StandardUnit.VOLT, 'watt':Units.StandardUnit.WATT, 'weber':Units.StandardUnit.WEBER}

def getEntityList(model, comp_name=None):
    # input: model, the CellML model object
    #        comp_name, the CellML component name
    # output: a list of the entity names.
    # if the component name is not provided, the list of the component names is returned;
    # if the component name is provided, the list of the variable names is returned
    if comp_name is None:
        return [model.component(comp_numb).name() for comp_numb in range(model.componentCount())]
    else:
        return [model.component(comp_name).variable(var_numb).name() for var_numb in range(model.component(comp_name).variableCount())]
    
def getEntityName_UI(model, comp_name=None):
    # input: model, the CellML model object
    #        comp_name, the CellML component name
    # output: the name of the entity.
    # if the component name is not provided, ask user to select the name from the component list and return the name of the component; 
    # if the component name is provided, ask user to select the name from the variable list and return the name of the variable
    if comp_name is None:
        message = 'Please select the component'
        choices = getEntityList(model)
        return ask_for_input(message, 'List', choices)
    else:
        message = 'Please select the variable'
        choices = getEntityList(model, comp_name)
        return ask_for_input(message, 'List', choices)

def getEntityID(model, comp_name=None, var_name=None):
    # input: model, the CellML model object
    #        comp_name, the CellML component name
    #        var_name, the CellML variable name
    # output: the ID of the entity.
    # if the component name is not provided, the ID of the model is returned; 
    # if the variable name is not provided, the ID of the component is returned; 
    # if both the component name and the variable name are provided, the ID of the variable is returned
    if comp_name is None:
        return model.id()
    elif var_name is None:
        return model.component(comp_name).id()
    else:
        return model.component(comp_name).variable(var_name).id()

#----------------------------------------------------------------------Build a CellML model from a csv file--------------------------------------------------------------
""" Read a csv file and create components and variables from it. """
def read_csv_UI():
    # Get the csv file from the user by opening a file dialog
    message='Please select the csv file to collect components:'
    file_path = ask_for_file_or_folder(message)
    return file_path

def read_csv(file_path):    
    # input: file_path: the path of the csv file
    # output: None, write the components and variables to a CellML model, saved as a .cellml file

    # Read the csv file and create components and variables from it
    df = pd.read_csv(file_path, sep=',', header=0, index_col=False,na_values='nan')
    df['component']=df['component'].fillna(method="ffill")
    gdf=df.groupby('component')
    params_comp = Component('param')
    components = []
    # Create CellML Variable for each variable in the component and add it to the component
        # Rules: 1. if the initial_value is nan, then the initial_value is None;
        #        2. if the param column is 'param', then the variable is a parameter and it will be added to the params list; 
        #           The initial_value of the variable will be None; 
        #           The initial_value of the parameter will be the value in the initial_value column;
        #        3. if the param column is init, then the variable is a state variable, and the variable name + '_init' will be added to the params list;
        #           The initial_value of the variable will be variable name + '_init'; 
        #           The initial_value of the parameter (variable name + '_init') will be the value in the initial_value column; 
    for component_name, groupi in gdf:
        component=Component(component_name)          
        for index, row in groupi.iterrows():
            units_name = row['units']
            var_name = row['variable']
            variable = Variable(var_name)
            units = Units(units_name)
            variable.setUnits(units)
            if pd.isna(row['initial_value']):
                pass
            elif row["param"]=='param':
                param = variable.clone()
                param.setInitialValue(row['initial_value'])
                params_comp.addVariable(param)                                             
            elif row['param'] == 'init':
                param = Variable(var_name+'_init')
                variable.setInitialValue(param)
                param.setUnits(units)
                param.setInitialValue(row['initial_value'])
                params_comp.addVariable(param)
            else:
                variable.setInitialValue(row['initial_value'])
            component.addVariable(variable)
                 
        components.append(component)
    
    if params_comp.variableCount()>0:        
        components.append(params_comp)
    
    # Write the components to a CellML file
    model_name = PurePath(file_path).stem
    full_path = PurePath(file_path).parent.joinpath(model_name+'.cellml')
    modeli = Model(model_name+'_comps')
    for component in components:
        modeli.addComponent(component)
    writeCellML(full_path,modeli)

    return components
   

"""" Parse a cellml file."""
def parseCellML(strict_mode=True):
    message='Please select the CellML file:'
    filename = ask_for_file_or_folder(message)   
    # Parse the CellML file
    existing_model=cellml.parse_model(filename, strict_mode)
    return filename, existing_model

def importCellML_UI(model_path,strict_mode=True):
    # input: model_path: the path of the CellML model that imports other CellML models
    #        strict_mode: whether to use strict mode when parsing the CellML model
    # output: imported_model: the existing model that is imported
    #         importSource: the ImportSource object
    #         import_type: the type of the import (units or components)
    #         imported_components_dict: a dictionary of the imported components, 
    #                                   with the key being the the new component name and the value being the original component name  
    import_action = ask_for_input('Do you want to import?', 'Confirm', True)
    imported_models,importSources,import_types, imported_components_dicts = [], [], [], []
    while import_action:
        filename, imported_model = parseCellML(strict_mode)
        relative_path=PurePath(filename).relative_to(model_path).as_posix()
        importSource = ImportSource()
        importSource.setUrl(relative_path)
        importSource.setModel(imported_model)
        message="Please select the component or units to import:"
        choices=['units', 'component']
        import_type = ask_for_input(message, 'List', choices)
        imported_components_dict = {}
        if import_type == 'component':
            message="Please select the components to import:"
            imported_components = ask_for_input( message, 'Checkbox', getEntityList(imported_model))
            for component in imported_components:
                message=f"If you want to rename the component {component}, please type the new name. Otherwise, just press 'Enter':"
                answer = ask_for_input(message, 'Text')
                if answer!='':
                    imported_components_dict.update({answer: component})
                else:
                    imported_components_dict.update({component:component})
        imported_models.append(imported_model)
        importSources.append(importSource)
        import_types.append(import_type)
        imported_components_dicts.append(imported_components_dict)
        import_action = ask_for_input('Do you want to continue?', 'Confirm', False)

    return  imported_models,importSources,import_types, imported_components_dicts

""" Import units or components from an existing CellML model. """
def importCellML(model,imported_model,importSource,import_type, imported_components_dict={}):
    # input: model: the model that imports other CellML models
    #        imported_model: the existing model that is imported
    #        importSource: the ImportSource object
    #        import_type: the type of the import (units or components)
    #        imported_components_dict: a dictionary of the imported components 
    # output: None
    #        The imported units or components will be added to the model          
    if import_type == 'units':
        units_undefined=_checkUndefinedUnits(model)
        if len(units_undefined)>0:
            # Get the intersection of the units_undefined and the units defined in the existing model
            existing_units=set([imported_model.units(unit_numb).name() for unit_numb in range(imported_model.unitsCount())])
            units_to_import = units_undefined.intersection(existing_units)
        else:
            units_to_import = set()
        for unit in units_to_import:
            u = Units(unit)
            u.setImportSource(importSource)
            u.setImportReference(unit)
            model.addUnits(u)
        print(f'The units {units_to_import} have been imported.')
    else:
        for component in imported_components_dict:
            c = Component(component)
            c.setImportSource(importSource)
            c.setImportReference(imported_components_dict[component])
            dummy_c = c.importSource().model().component(c.importReference()).clone()
            while(dummy_c.variableCount()):
                 c.addVariable(dummy_c.variable(0))
            model.addComponent(c) 

def encapsulate_UI(model):
    # input: model: the model object that includes the components to be encapsulated
    # output: component_parent_selected: the name of the parent component
    #         component_children_selected: a list of the names of the children components
    confirm =ask_for_input('Do you want to encapsulate components', 'Confirm', False)
    if confirm: 
        message="Please select the parent component:"
        component_list = getEntityList(model)
        component_parent_selected = ask_for_input(message, 'List', component_list)
        message="Please select the children components:"
        choices=[comp_name for comp_name in component_list if comp_name != component_parent_selected]
        component_children_selected = ask_for_input(message, 'Checkbox', choices)
    else:
        component_parent_selected = []
        component_children_selected = []
    return component_parent_selected, component_children_selected

""" Carry out the encapsulation. """
def encapsulate(model, component_parent_selected, component_children_selected):
    # input: model: the model object that includes the components to be encapsulated
    #        component_parent_selected: the name of the parent component
    #        component_children_selected: a list of the names of the children components
    # output: None
    #        The encapsulation will be added to the model
    for component_child in component_children_selected:
        model.component(component_parent_selected).addComponent(model.component(component_child))


""" Find the variables that are mapped in two components. """
def _findMappedVariables(comp1,comp2):
    # input: comp1: the first component
    #        comp2: the second component
    # output: mapped_variables_comp1: a list of the names of the variables in comp1 that are mapped to variables in comp2
    #         mapped_variables_comp2: a list of the names of the variables in comp2 that are mapped to variables in comp1
    mapped_variables_comp1 = []
    mapped_variables_comp2 = []
    for v in range(comp1.variableCount()):
        if comp1.variable(v).equivalentVariableCount()>0:
            for e in range(comp1.variable(v).equivalentVariableCount()):
                ev = comp1.variable(v).equivalentVariable(e)
                if ev is None:
                    print("WHOOPS! Null equivalent variable!")
                    continue               
                ev_parent = ev.parent()
                if ev_parent is None:
                    print("WHOOPS! Null parent component for equivalent variable!")
                    continue  
                if ev_parent.name() == comp2.name():
                    mapped_variables_comp1.append(comp1.variable(v).name())
                    mapped_variables_comp2.append(ev.name())
    return mapped_variables_comp1, mapped_variables_comp2
                    

"""" Provide variable connection suggestion based on variable name and carry on the variable mapping based on user inputs. """
def suggestConnection(model,comp1,comp2):
    # Get the variables in the two components
    variables1 = [comp1.variable(var_numb).name() for var_numb in range(comp1.variableCount())]
    variables2 = [comp2.variable(var_numb).name() for var_numb in range(comp2.variableCount())]
    print('The variables in the first component are:', variables1)
    print('The variables in the second component are:', variables2)
    # Get the intersection of the variable names in the two components
    variables = set(variables1).intersection(variables2)
    if len(variables)>0:
        print('The variable names that are shared by the two components are:', variables)
        message="Please select the variables to map. If you want to map all the variables, just press 'Enter'"
        choices=[var for var in variables]
        answers = ask_for_input( message, 'Checkbox', choices)
        if len(answers)>0:
            for var in answers:
                if Units.compatible(model.component(comp1).variable(var).units(), model.component(comp2).variable(var).units()):
                    Variable.addEquivalence(comp1.variable(var), comp2.variable(var))
                else:
                    print(f'{var} has units {comp1.variable(var).units()} in comp1 but {comp2.variable(var).units()} in comp2, which are not compatible.')
                
        else:
            for var in variables:
                if Units.compatible(model.component(comp1).variable(var).units(), model.component(comp2).variable(var).units()):
                    Variable.addEquivalence(comp1.variable(var), comp2.variable(var))
                else:
                    print(f'{var} has units {comp1.variable(var).units()} in comp1 but {comp2.variable(var).units()} in comp2, which are not compatible.')
    # Get the variables in the two components that are not sharing the same name
    variables1 = [comp1.variable(var_numb).name() for var_numb in range(comp1.variableCount()) if comp1.variable(var_numb).name() not in variables]
    variables2 = [comp2.variable(var_numb).name() for var_numb in range(comp2.variableCount()) if comp2.variable(var_numb).name() not in variables]
    if len(variables1)>0:
        message="Please select the unmapped variables in the first component to clone and map:"
        choices=[var for var in variables1]
        answers = ask_for_input( message, 'Checkbox', choices)
        for var in answers:
            comp2.addVariable(comp1.variable(var).clone())
            Variable.addEquivalence(comp1.variable(var), comp2.variable(var))     
    if len(variables2)>0:    
        message="Please select the unmapped variables in the second component to clone and map:"
        choices=[var for var in variables2]
        answers = ask_for_input( message, 'Checkbox', choices)
        for var in answers:
            comp1.addVariable(comp2.variable(var).clone())
            Variable.addEquivalence(comp1.variable(var), comp2.variable(var))
    # Keep mapping the variables in the two components that are not mapped
    while True:
        mapped_variables_comp1, mapped_variables_comp2= _findMappedVariables(comp1,comp2)
        unmapped_variables_comp1 = [comp1.variable(v).name() for v in range(comp1.variableCount()) if comp1.variable(v).name() not in mapped_variables_comp1]
        unmapped_variables_comp2 = [comp2.variable(v).name() for v in range(comp2.variableCount()) if comp2.variable(v).name() not in mapped_variables_comp2]
        if len(unmapped_variables_comp1)>0 and len(unmapped_variables_comp2)>0:
            message="Please select one variable in comp1 and another in comp2 to map or Enter to skip"
            choices=[f'comp1:{var}' for var in unmapped_variables_comp1] + [f'comp2:{var}' for var in unmapped_variables_comp2]
            answers = ask_for_input( message, 'Checkbox', choices)
            if len(answers)>0:
                var1 = answers[0].split(':')[1]
                var2 = answers[1].split(':')[1]
                if Units.compatible(model.component(comp1).variable(var).units(), model.component(comp2).variable(var).units()):
                    Variable.addEquivalence(comp1.variable(var), comp2.variable(var))
                else:
                    print(f'{var} has units {comp1.variable(var).units().name()} in comp1 but {comp2.variable(var).units().name()} in comp2, which are not compatible.')
            else:
                break
        else:
            break
    # Get the variables in the two components that are mapped but both have initial values; ask the user to select the initial value to keep
    mapped_variables_comp1, mapped_variables_comp2= _findMappedVariables(comp1,comp2)
    for var1,var2 in zip(mapped_variables_comp1, mapped_variables_comp2):
        if (comp1.variable(var1).initialValue()!='') and (comp2.variable(var2).initialValue()!= '') :
            message = f'var {var1} in {comp1.name()} with init: {comp1.variable(var1).initialValue()}\n    var {var2} in {comp2.name()} init: {comp2.variable(var2).initialValue()} \n Please select the initial value to keep:'
            choices=[comp1.name(), comp2.name()]
            answer = ask_for_input(message, 'Checkbox', choices)
            if comp1.name() not in answer:
                comp1.variable(var1).removeInitialValue()
            if  comp2.name() not in answer:
                comp2.variable(var2).removeInitialValue()

""" Carry out the connection. """
def connect(base_dir,model):
    importer = cellml.resolve_imports(model, base_dir, True)
    flatModel = importer.flattenModel(model) # this may not be necessary after the units compatibility check function is fixed
    # List the components in the model
    components = getEntityList(model)
    # Find the components that have encapsulated components, and connect the parent and children components
    def suggestConnection_parent_child(parent_component):
        if parent_component.componentCount()>0:
            for child_numb in range(parent_component.componentCount):                
                child_component = parent_component.component(child_numb)
                suggestConnection(flatModel,parent_component, child_component)
                suggestConnection_parent_child(child_component)

    for comp_numb in range(model.componentCount()):
        parent_component = model.component(comp_numb)
        suggestConnection_parent_child(parent_component)
        
    while True:
        message = 'Please select two components to connect or Enter to skip:'
        answer = ask_for_input(message, 'Checkbox', components)       
        if len(answer)>0:
            comp1= answer[0]
            comp2= answer[1]
            suggestConnection(flatModel, model.component(comp1), model.component(comp2))
        else:
            break
"""Check the undefined non base units"""
def _checkUndefinedUnits(model):
    # inputs:  a model object
    # outputs: a set of undefined units
    units_claimed = set()
    for comp_numb in range(model.componentCount()):
        for var_numb in range(model.component(comp_numb).variableCount()):
            if model.component(comp_numb).variable(var_numb).units().name() != '':
                if  not (model.component(comp_numb).variable(var_numb).units().name() in BUILTIN_UNITS.keys()):
                    units_claimed.add(model.component(comp_numb).variable(var_numb).units().name())

    units_defined = set()
    for unit_numb in range(model.unitsCount()):
        # print(model.units(unit_numb).name())
        units_defined.add(model.units(unit_numb).name()) 
    units_undefined = units_claimed - units_defined
    return units_undefined

def defineUnits_UI(iunitsName):
    print(f'Please define the units {iunitsName}:')
    message = 'Please type the name of the standardUnit or press Enter to skip:'
    unitName = ask_for_input(message, 'Text')
    message = 'Please type the prefix or press Enter to skip:'
    prefix = ask_for_input(message, 'Text')
    message = 'Please type the exponent or press Enter to skip:'
    exponent = ask_for_input(message, 'Text')
    message = 'Please type the multiplier or press Enter to skip:'
    multiplier = ask_for_input(message, 'Text')
    return unitName, prefix, exponent, multiplier

# Define the units
def _defineUnits(iunitsName):
    iunits = Units(iunitsName)
    while True:
        unitName, prefix, exponent, multiplier = defineUnits_UI(iunitsName)
        if unitName == '':
            break
        else:    
            if exponent != '':
                exponent = float(exponent)
            else:
                exponent = 1.0
            if multiplier != '':
                multiplier = float(multiplier)
            else:
                multiplier = 1.0   
            if prefix == '':
                prefix = 1   
            if unitName in BUILTIN_UNITS:
                iunits.addUnit(BUILTIN_UNITS[unitName], prefix, exponent, multiplier)
            else:
                iunits.addUnit(unitName,prefix, exponent, multiplier)                
    return iunits

# Add units to the model
def addUnits_UI(model):
    units_undefined=_checkUndefinedUnits(model)
    print('The units claimed in the variables but undefined are:',units_undefined)
    # Ask the user to add the units which are claimed in the variables but not defined in the model
    for units in units_undefined:
        while True:
            message = 'Do you want to add units:' + units + '?'
            answer = ask_for_input(message, 'Confirm', True)           
            if answer:
                iunits=_defineUnits(units)
                model.addUnits(iunits)
            else:
                break
    # Ask the user to add custom units
    while True:
        message = 'Please type the name of a custom units or pressEnter to skip:'
        answers = ask_for_input(message, 'Text')
        if answers!= '':
            iunits=_defineUnits(answers)
            model.addUnits(iunits)    
        else:
            break              
    # Replace the units with the standard units
# Write the equations to a component
def writeEquations_UI(component):
    while True:
        message = 'Please type the lefthand of the equation or press Enter to skip:'
        ode_var = ask_for_input(message, 'Text')
        if ode_var != '':            
            message = 'Please type the righthand of the equation:'
            infix = ask_for_input(message, 'Text')
            message = 'Please type the the variable of integration or press Enter to skip:'
            voi = ask_for_input(message, 'Text')
            component. appendMath(infix_to_mathml(infix, ode_var, voi))
        else:
            break

# Add equations to the model
def addEquations(component, equations):

    component.setMath(MATH_HEADER)            
    for equation in equations:
        infix = equation[0]
        ode_var = equation[1]
        voi = equation[2]
        component. appendMath(infix_to_mathml(infix, ode_var, voi))
    component. appendMath(MATH_FOOTER)


def writeCellML_UI(directory, model):
    message = f'If you want to change the default filename {model.name()}.cellml, please type the new name. Otherwise, just press Enter.'
    file_name = ask_for_input(message, 'Text')
    if file_name == '':
        file_name=model.name()+'.cellml'
    else:
        file_name=file_name+'.cellml'
    full_path = str(PurePath(directory).joinpath(file_name))
    return full_path

# Write a model to cellml file, input: directory, model, output: cellml file
def writeCellML(full_path, model): 
    full_path= assignAllIds(full_path,model)    
    printer = Printer()
    serialised_model = printer.printModel(model)    
    write_file = open(full_path, "w")
    write_file.write(serialised_model)
    write_file.close()
    print('CellML model saved to:',full_path)

def writePythonCode_UI(directory, model):
    message = f'If you want to change the default filename {model.name()}.py, please type the new name. Otherwise, just press Enter.'
    file_name = ask_for_input(message, 'Text')
    if file_name == '':
        file_name=model.name()+'.py'
    else:
        file_name=file_name+'.py'
    full_path = str(PurePath(directory).joinpath(file_name))  
    return full_path
      
""""Write python code for the complete model"""
def writePythonCode(full_path, model,strict_mode=True):
    base_dir = PurePath(full_path).parent
    importer = cellml.resolve_imports(model, base_dir, strict_mode)
    flatModel = importer.flattenModel(model)
    a = cellml.analyse_model(flatModel)              
    generator = Generator()
    generator.setModel(a)
    profile = GeneratorProfile(GeneratorProfile.Profile.PYTHON)
    generator.setProfile(profile)
    implementation_code_python = generator.implementationCode()                   
    # Save the python file in the same directory as the CellML file
    with open(full_path, "w") as f:
        f.write(implementation_code_python)
    print('Python code saved to:', full_path)

""""Edit the model based on the user input"""
def editModel(directory,model):
    imported_models,importSources,import_types, imported_components_dicts = importCellML_UI(directory)
    for i in range(len(imported_models)):
        importCellML(model,imported_models[i],importSources[i],import_types[i], imported_components_dicts[i])

    addUnits_UI(model)
    component_parent_selected, component_children_selected=encapsulate_UI(model)
    encapsulate(model, component_parent_selected, component_children_selected)
    connect(directory,model)
    model.fixVariableInterfaces()
    if model.hasUnlinkedUnits():
        model.linkUnits()
    #    Create a validator and use it to check the model so far.
    print_model(model,True)
    cellml.validate_model(model)
    

"""" Assign IDs to all entities in the model; """
def assignAllIds(fullpath,model):
    meassage = f'Do you want to assign all the ids to the {model.name()}?'
    answer = ask_for_input(meassage, 'Confirm', True)
    if answer:
        directory=str(PurePath(fullpath).parent)
        annotator = Annotator()
        annotator.setModel(model)
        annotator.clearAllIds()
        annotator.assignAllIds()
        duplicates = annotator.duplicateIds()
        """"
        if len(duplicates) > 0: # aways true
            print('There are duplicate IDs. Assigning new IDs to all entities.')
            annotator.clearAllIds()
            annotator.assignAllIds()
            # Save the updated model to a new file - the filename is the original one + '_newIDs'
            filename = str(PurePath(fullpath).stem)+'_newIDs.cellml'
            fullpath = str(PurePath(directory).joinpath(filename))
            writeCellML(fullpath, model)
        """
    return fullpath    

""" Create a model from a list of components. """
def buildModel():
    message = 'Start building a model from csv file or an existing model?'
    choices = ['csv file', 'existing model']
    choice = ask_for_input(message, 'List', choices)

    if choice == 'csv file':
        file_path=read_csv_UI()
        components=read_csv(file_path)    
    else:
        filename, existing_model=parseCellML
        components= getEntityList(existing_model)
    
    message="Please type the model name:"
    model_name = ask_for_input(message, 'Text')
    message = 'Please select the folder to save the model:'
    directory = ask_for_file_or_folder(message,True)

    while True:
        if model_name!= '':           
            model = Model(model_name)
            message="Select the components to add to the model:"
            choices=[str(components.index(component))+ ":"+ component.name() for component in components]
            components_selected = ask_for_input(message, 'Checkbox', choices)
            indexes = [int(i.split(':')[0]) for i in components_selected]
            for index in indexes:
                model.addComponent(components[index].clone())
            
            editModel(model)

            message="Do you want to save the model?"
            answer = ask_for_input(message, 'Confirm', True)
            if answer:
                full_path=writeCellML_UI(directory, model)
                writeCellML(full_path, model)
                full_path=writePythonCode_UI(directory, model)
                writePythonCode(full_path, model)
            
            message="Please type the model name or press Enter to quit building models:"
            model_name = ask_for_input(message, 'Text')                               
        else:
            break
            
# main function
if __name__ == "__main__":
    buildModel()


