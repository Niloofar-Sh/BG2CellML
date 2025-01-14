from libcellml import Component, Model, Units,  Variable, ImportSource
from utilities import  ask_for_file_or_folder, ask_for_input, load_matrix, infix_to_mathml
import sys
from pathlib import PurePath
from build_CellMLV2 import editModel, MATH_FOOTER, MATH_HEADER,addEquations, _defineUnits,parseCellML,writeCellML,writeCellML_UI, importCellML,importCellML_UI
from sympy import *
import numpy as np
from itertools import combinations
import networkx as nx

R,T,V_m, F, E=symbols('R,T,V_m, F, E')
#---------------------------------------------------------------Build a cellML model for BG----------------------------------------------------------#
"""Define BG component class"""
class BG():
    # Define physical domain and corresponding effort and flow variables, and their units
    dom = {'Ch':{'e':['mu','J_per_mol'],'f':['v','fmol_per_sec'],'q':['q','fmol']}, 
          'E':{'e':['V','volt'],'f':['I','fA'],'q':['q','fC']}} 
    # Define component and corresponding parameters, and their units
    comp = {'Ce':{'dom':'Ch', 'description':'Chemical species', 'para':['K','per_fmol']},
            'Se':{'dom':'Ch','description':'Chemostat', 'para':['K','per_fmol']},
            'C':{'dom':'E', 'description':'Capacitor','para':['C','fF']},
            'Ve':{'dom':'E','description':'Voltage source', 'para':['C','fF']},
            'Re':{'dom':'Ch','description':'Chemical Reaction', 'para':['kappa','fmol_per_sec']},
            'Re_GHK':{'dom':'Ch','description':'GHK Reaction', 'para':['kappa','fmol_per_sec']},
            'R':{'dom':'E','description':'Resistor', 'para':['g','fS']} }
    # Define constant value and their units
    const = {'F':[96485,'C_per_mol'], 'R':[8.31,'J_per_K_per_mol'], 'T':[293, 'kelvin']}
    # Define the default units for material quantity q, flow f, and effort e of each domain
    # Biochemical domain
    q_Ch_1 = Units('fmol')
    q_Ch_1.addUnit(Units.StandardUnit.MOLE, 'femto')
    v_Ch_1 = Units('fmol_per_sec')
    v_Ch_1.addUnit(Units.StandardUnit.MOLE, 'femto')
    v_Ch_1.addUnit(Units.StandardUnit.SECOND, 1, -1)
    mu_Ch_1 = Units('J_per_mol')
    mu_Ch_1.addUnit(Units.StandardUnit.JOULE)
    mu_Ch_1.addUnit(Units.StandardUnit.MOLE, 1, -1)
    q_Ch_2 = Units('mM')
    q_Ch_2.addUnit(Units.StandardUnit.MOLE, 'milli')
    q_Ch_2.addUnit(Units.StandardUnit.LITRE, 1, -1)
    v_Ch_2 = Units('mM_per_sec')
    v_Ch_2.addUnit(Units.StandardUnit.MOLE, 'milli')
    v_Ch_2.addUnit(Units.StandardUnit.LITRE, 1, -1)
    v_Ch_2.addUnit(Units.StandardUnit.SECOND, 1, -1)
    mu_Ch_2 = Units('J_per_mM')
    mu_Ch_2.addUnit(Units.StandardUnit.JOULE)
    mu_Ch_2.addUnit(Units.StandardUnit.MOLE,'milli', -1)
    mu_Ch_2.addUnit(Units.StandardUnit.LITRE)
    # Electrical domain
    q_E_1 = Units('fC')
    q_E_1.addUnit(Units.StandardUnit.COULOMB, 'femto')
    v_E_1 = Units('fA')
    v_E_1.addUnit(Units.StandardUnit.AMPERE, 'femto')
    v_E_1.addUnit(Units.StandardUnit.SECOND, 1, -1)
    # mu_E_1 = Units('volt') # volt is the default unit for effort, so no need to define it

"""Add variables and equations based on the component type"""
def add_BGcomp(model, name, type, voi = 't'):   
    if type not in list(BG.comp):
       sys.exit(f'BG {type} is not defined!')
    component = model.component(model.name())
    component_param = model.component(model.name()+ '_param')
    dom = BG.comp[type]['dom']
    para_name = BG.comp[type]['para'][0] + '_' + name
    para_unit = Units(BG.comp[type]['para'][1])
    para=Variable(para_name)
    para.setUnits(para_unit)
    component.addVariable(para)
    component_param.addVariable(para.clone())
    f_name = BG.dom[dom]['f'][0]+ '_' + name
    f_unit = Units(BG.dom[dom]['f'][1])
    f=Variable(f_name)
    f.setUnits(f_unit)
    component.addVariable(f)
    if type in ['Ce','Se','C','Ve']:          
        q_init_name = BG.dom[dom]['q'][0]+ '_' + name + '_init'
        q_unit = Units(BG.dom[dom]['q'][1])
        q_init=Variable(q_init_name)
        q_init.setUnits(q_unit)
        component.addVariable(q_init)
        component_param.addVariable(q_init.clone())
        q_name = BG.dom[dom]['q'][0]+ '_' + name
        q=Variable(q_name)
        q.setUnits(q_unit)
        q.setInitialValue(q_init)
        component.addVariable(q)
        e_name = BG.dom[dom]['e'][0]+ '_' + name
        e_unit = Units(BG.dom[dom]['e'][1])
        e=Variable(e_name)
        e.setUnits(e_unit)
        component.addVariable(e)
        if type in ['Ce','Se']:   
           eq = f'R*T*ln({para.name()}*{q.name()})'
        else: # 'C','Ve'
           eq = f'{f.name()}/{para.name()}'
        ode_var = f'{e.name()}'          
        component.appendMath(infix_to_mathml(eq, ode_var))
        if type in ['Ce','C']:
           ode_var = f'{q.name()}'
           eq = f'{f.name()}'
           component.appendMath(infix_to_mathml(eq, ode_var, voi))                    
    elif type == 'Re':
        ein_name = BG.dom[dom]['e'][0]+ '_' + name+ '_in'
        eout_name = BG.dom[dom]['e'][0]+ '_' + name+ '_out'
        e_unit = Units(BG.dom[dom]['e'][1])
        ein=Variable(ein_name)
        eout=Variable(eout_name)
        ein.setUnits(e_unit)
        eout.setUnits(e_unit)
        component.addVariable(ein)
        component.addVariable(eout)
        eq = f'{para.name()}*(exp({ein.name()}/(R*T))-exp({eout.name()}/(R*T)))'
        ode_var = f'{f.name()}'
        component.appendMath(infix_to_mathml(eq, ode_var))
    else:
        sys.exit(f'BG {type} is not defined!')

""""Add equations based on the connection matrices"""
def add_BGbond(model, comps, compd, Nf, Nr):
    # Add the zero nodes, i.e., mass balance equations
    component = model.component(model.name())
    for i,ecomp in enumerate(comps):
        name = ecomp[0]
        type = ecomp[1]
        dom = BG.comp[type]['dom']
        f_name = BG.dom[dom]['f'][0]+ '_' + name
        ode_var = f'{f_name}'
        eq = []
        for j in range(len(Nf[0,:])):
            if Nf[i,j] != '0':
                name = compd[j][0]
                type = compd[j][1]
                dom = BG.comp[type]['dom']
                f_name = BG.dom[dom]['f'][0]+ '_' + name
                if Nf[i,j] == '1':
                    eq.append(f'-{f_name}')
                else:
                    eq.append(f'-{Nf[i,j]}*{f_name}')
        for j in range(len(Nr[0,:])):
            if Nr[i,j] != '0':
                name = compd[j][0]
                type = compd[j][1]
                dom = BG.comp[type]['dom']
                f_name = BG.dom[dom]['f'][0]+ '_' + name
                if Nr[i,j] == '1':
                    if len(eq) == 0:
                        eq.append(f'{f_name}')
                    else:
                        eq.append(f'+{f_name}')
                else:
                    if len(eq) == 0:
                        eq.append(f'{Nr[i,j]}*{f_name}')
                    else:
                        eq.append(f'+{Nr[i,j]}*{f_name}')
                        
        component.appendMath(infix_to_mathml(''.join(eq), ode_var))
    # Add the one nodes, i.e., energy balance equations
    for j,dcomp in enumerate(compd):
        name = dcomp[0]
        type = dcomp[1]
        dom = BG.comp[type]['dom']
        ein_name = BG.dom[dom]['e'][0]+ '_' + name+ '_in'
        eout_name = BG.dom[dom]['e'][0]+ '_' + name+ '_out'
        eqout = []
        eqin = []
        ode_var_out = f'{eout_name}'
        ode_var_in = f'{ein_name}'
        for i in range(len(Nf[:,0])):
            if Nf[i,j] != '0':
                name = comps[i][0]
                type = comps[i][1]
                dom = BG.comp[type]['dom']
                e_name = BG.dom[dom]['e'][0]+ '_' + name
                if Nf[i,j] == '1':
                    if len(eqin) == 0:
                        eqin.append(f'{e_name}')
                    else:
                        eqin.append(f'+{e_name}')
                else:
                    if len(eqin) == 0:
                        eqin.append(f'{Nf[i,j]}*{e_name}')
                    else:
                        eqin.append(f'+{Nf[i,j]}*{e_name}')
        for i in range(len(Nr[:,0])):
            if Nr[i,j] != '0':
                name = comps[i][0]
                type = comps[i][1]
                dom = BG.comp[type]['dom']
                e_name = BG.dom[dom]['e'][0]+ '_' + name
                if Nr[i,j] == '1':
                    if len(eqout) == 0:
                        eqout.append(f'{e_name}')
                    else:
                        eqout.append(f'+{e_name}')
                else:
                    if len(eqout) == 0:
                        eqout.append(f'{Nr[i,j]}*{e_name}')
                    else:
                        eqout.append(f'+{Nr[i,j]}*{e_name}')

        component.appendMath(infix_to_mathml(''.join(eqin), ode_var_in))
        component.appendMath(infix_to_mathml(''.join(eqout), ode_var_out))

"""Read bond graph model from a csv file and create a CellML model from it."""
def read_csvBG():
    # Get the csv file from the user by opening a file dialog
    message='Please select the forward matrix csv file:'
    file_name_f = ask_for_file_or_folder(message)
    directory = PurePath(file_name_f).parent
    # by default, the reverse matrix csv file is the same as the forward matrix csv file expect that the file name ends with '_r'
    file_name_r = file_name_f[:-6]+'_r.csv' 
    # Read the csv file, which has two rows of headers, the first row is the reaction type and the second row is the reaction name
    CompName,CompType,ReName,ReType,N_f,N_r=load_matrix(file_name_f,file_name_r)
    # Get the default model names: BG_filename, BG_filename_param, BG_filename_test = BG_filename + BG_filename_param, 
    # Steady state model names: ss_filename (ss expression), BG_ss_filename_param (link BG parameters to simplified parameters),  
    # ss_filename_param (simplified parameters), 
    # BG_ss_filename_test = (ss_filename + BG_ss_filename_param + BG_filename_param) , ss_filename_test = (ss_filename + ss_filename_param)
    name_f=PurePath(file_name_f).stem.split('_')[0]
    model_BG = Model('BG_'+ name_f)
    model_BG_param = Model('BG_'+ name_f + '_param')
    model_BG_test = Model('BG_'+ name_f + '_test')
    model_ss = Model('ss_'+ name_f)
    model_ss_param = Model('ss_'+ name_f + '_param')
    model_ss_test = Model('ss_'+ name_f + '_test')
    model_BG_ss_test = Model('BG_ss_'+ name_f + '_test')
    model_BG_ss_param = Model ('BG_ss_'+ name_f + '_param')
    # Default voi, units, and init
    voi = 't'
    units = Units('second')
    voi = Variable(voi)
    voi.setUnits(units)
    # Build model_BG
    component=Component(model_BG.name())
    component_param=Component(model_BG_param.name())
    model_BG.addComponent(component)
    model_BG.addComponent(component_param)
    component.addVariable(voi)
    component.setMath(MATH_HEADER)              
    for i, comp in enumerate(CompName):
        add_BGcomp(model_BG, comp, CompType[i],voi.name())
    for i, re in enumerate(ReName):
        add_BGcomp(model_BG, re, ReType[i],voi.name())
    comps = list(zip(CompName,CompType))
    compd = list(zip(ReName,ReType))
    add_BGbond(model_BG, comps, compd, N_f, N_r)
    component.appendMath(MATH_FOOTER)
    # Remove component_param from model_BG
    component_param_clone = model_BG.component(model_BG_param.name()).clone()
    model_BG.removeComponent(model_BG_param.name())
    # Build model_BG_param
    model_BG_param.addComponent(component_param_clone)
   
    # Set the default parameters as 1
    for var_numb in range(component_param_clone.variableCount()):
        model_BG_param.component(component_param_clone.name()).variable(var_numb).setInitialValue(1)

    # Add the constant variables    
    for const in BG.const:
        const_name = const
        var_const=Variable(const_name)
        unit_name = BG.const[const_name][1]
        u=Units(unit_name)
        var_const.setUnits(u)
        param_const = var_const.clone()
        param_const.setInitialValue(BG.const[const_name][0])
        model_BG.component(component.name()).addVariable(var_const)
        model_BG_param.component(component_param_clone.name()).addVariable(param_const)

    vss_num,vss_den =  flux_ss_diagram(CompName,CompType,ReName,ReType,N_f,N_r)
    v_ss_simplified, P, Q = simplify_flux_ss(vss_num,vss_den)
    # Build model_ss
    unitsSet = set()
    component_ss=Component(model_ss.name())
    vss_equation =[(str(v_ss_simplified),'v_ss','')]
    P_equations=[]
    v_ss = Variable('v_ss')
    v_ss.setUnits(BG.v_Ch_1)

    for param in P:
        var_param=Variable(param.name)
        unit_name = P[param][1]
        u=Units(unit_name)
        unitsSet.add(unit_name)
        var_param.setUnits(u)
        component_ss.addVariable(var_param)
        ode_var= param.name
        infix = str(P[param][0])
        P_equations.append((infix,ode_var,''))
    
    component_BG_ss = component_ss.clone() # P is the simplified parameters

    for q in Q:
        var_q=Variable(q.name)
        unit_name = Q[q][1]
        u=Units(unit_name)
        unitsSet.add(unit_name)
        var_q.setUnits(u)
        component_ss.addVariable(var_q)  

    
    component_ss_param=component_ss.clone() # P, Q are the simplified parameters
    component_ss.addVariable(v_ss) # v_ss is the simplified flux
    
    # Add the units to the units model
    print('Adding units to the units model file...')
    filename, existing_model = parseCellML()
    relative_path=PurePath(filename).relative_to(directory).as_posix()
    importSource = ImportSource()
    importSource.setUrl(relative_path) 
    imported_models=[existing_model]
    importSources=[importSource]
    import_types=['units']
    units_defined = set()
    for unit_numb in range(existing_model.unitsCount()):
        units_defined.add(existing_model.units(unit_numb).name()) 
    units_undefined = unitsSet - units_defined

    for iunitsName in units_undefined:
        inunits=_defineUnits(iunitsName)
        existing_model.addUnits(inunits)        
    writeCellML(filename, existing_model)

    for var_num in range(component_ss_param.variableCount()):
        component_ss_param.variable(var_num).setInitialValue(1)

    model_ss_param.addComponent(component_ss_param)

    addEquations(component_ss, vss_equation)
    model_ss.addComponent(component_ss) # v_ss is the simplified flux, P is the simplified parameters

    for var_num in range(component_param_clone.variableCount()):
        component_BG_ss.addVariable(component_param_clone.variable(var_num).clone())

    component_BG_ss.removeVariable(v_ss)
    addEquations(component_BG_ss, P_equations)

    
    model_BG_ss_param.addComponent(component_BG_ss)
   
    print('model_BG, only import the units')
    importCellML(model_BG,imported_models[0],importSources[0],import_types[0], imported_components_dict={})
    editModel(directory,model_BG)
    fullpath=writeCellML_UI(directory, model_BG)
    writeCellML(fullpath, model_BG)
    
    print('model_BG_param, import the units')
    importCellML(model_BG_param,imported_models[0],importSources[0],import_types[0], imported_components_dict={})
    editModel(directory,model_BG_param)
    fullpath=writeCellML_UI(directory, model_BG_param)
    writeCellML(fullpath, model_BG_param)
    
    print('model_BG_ss, import the units')
    importCellML(model_ss,imported_models[0],importSources[0],import_types[0], imported_components_dict={})
    editModel(directory,model_ss)
    fullpath=writeCellML_UI(directory, model_ss)
    writeCellML(fullpath, model_ss)
   
    print('model_ss_param, import the units')
    importCellML(model_ss_param,imported_models[0],importSources[0],import_types[0], imported_components_dict={})
    editModel(directory,model_ss_param)
    fullpath=writeCellML_UI(directory, model_ss_param)
    writeCellML(fullpath, model_ss_param)
    
    print('model_BG_ss_param, import the units')
    importCellML(model_BG_ss_param,imported_models[0],importSources[0],import_types[0], imported_components_dict={})
    editModel(directory,model_BG_ss_param)
    fullpath=writeCellML_UI(directory, model_BG_ss_param)
    writeCellML(fullpath, model_BG_ss_param)
   
    print('model_BG_test, import the model_BG and model model_BG_param')
    importCellML(model_BG_test,imported_models[0],importSources[0],import_types[0], imported_components_dict={})
    editModel(directory,model_BG_test)
    fullpath=writeCellML_UI(directory, model_BG_test)
    writeCellML(fullpath, model_BG_test)
    
    print('model_ss_test, import the model_ss and model model_ss_param')
    importCellML(model_ss_test,imported_models[0],importSources[0],import_types[0], imported_components_dict={})
    editModel(directory,model_ss_test)
    fullpath=writeCellML_UI(directory, model_ss_test)
    writeCellML(fullpath, model_ss_test)
   
    print('model_BG_ss_test, import the model_BG_ss, model model_BG_ss_param and model_BG_param')
    importCellML(model_BG_ss_test,imported_models[0],importSources[0],import_types[0], imported_components_dict={})
    editModel(directory,model_BG_ss_test)
    fullpath=writeCellML_UI(directory, model_BG_ss_test)
    writeCellML(fullpath, model_BG_ss_test)
    

""" From the stoichiometric matrix to derive the steady state equations"""
def flux_ss(CompName,CompType,ReName,ReType,N_f,N_r):
    # Note: cannot handle large matrix due to performance issue
    # define lambda functions to apply to the entries of matrix
    f_exp = lambda x: exp(x)
    f_log = lambda x: log(x)
    # convert the string stoichiometric matrix to float matrix. TODO: need to handle the case of stoichiometric matrix with symbolic entries   
    Nf = nsimplify(Matrix(np.array(N_f,dtype=float)))
    Nr = nsimplify(Matrix(np.array(N_r,dtype=float)))
    # Get the quantities q, thermal parameters K, of the species
    q = Matrix([Symbol(f'q_{comp}') for comp in CompName])
    K_cd=diag(*[Symbol(f'K_{comp}') for i,comp in enumerate(CompName) if CompType[i]=='Ce'])
    K_cs=diag(*[Symbol(f'K_{comp}') for i,comp in enumerate(CompName) if CompType[i]=='Se'])
    # Get the reaction rate constants kappa
    kappa = diag(*[Symbol(f'kappa_{re}') for re in ReName])
    # Split the matrices into 3 parts: the first part is the chemostatic, the second part is the chemodynamic, the third part is the electrical charge if any  
    chemostatic_index = [i for i, x in enumerate(CompType) if x == 'Se']
    chemodynamic_index = [i for i, x in enumerate(CompType) if x == 'Ce']
    electrogenic_index = [i for i, x in enumerate(CompType) if x == 'Ve']
    N_cs_f = Matrix(Nf[chemostatic_index,:])
    N_cs_r = Matrix(Nr[chemostatic_index,:])
    N_cd_f = Matrix(Nf[chemodynamic_index,:])
    N_cd_r = Matrix(Nr[chemodynamic_index,:])
    q_cs = q[chemostatic_index,:]
    N_cd = N_cd_r-N_cd_f 
    # Get the chemical potentials and electrical potential (converted to chemical potential)   
    mu_cs = R*T*((K_cs*q_cs).applyfunc(f_log))
    if len(electrogenic_index)>0:
        N_e_f = Matrix(Nf[electrogenic_index,:])
        N_e_r = Matrix(Nr[electrogenic_index,:])
        mu_e = Matrix([F*V_m for i in range(len(electrogenic_index))])
        mu_source = mu_cs.col_join(mu_e)
        N_source_f = N_cs_f.col_join(N_e_f)
        N_source_r = N_cs_r.col_join(N_e_r)
    else:
        mu_source = mu_cs
        N_source_f = N_cs_f
        N_source_r = N_cs_r
    # Construct the matrices B_f and B_r which encode the potentials impact on the reaction rates
    B_f=diag(*((N_source_f.T *(mu_source/(R*T))).applyfunc(f_exp)))
    B_r=diag(*((N_source_r.T *(mu_source/(R*T))).applyfunc(f_exp)))
    # Construct the matrix M and vector b for the linear equations
    # b is a vector containing N number of 0s and the last entry is E; N is the number of reactions minus 1
    b = Matrix([0 for i in range(Nf.shape[1]-1)]+[E])
    M_ss=N_cd*(kappa*(B_f*N_cd_f.T-B_r*N_cd_r.T)*K_cd)
    M_G = Matrix([[1 for i in range(len(chemodynamic_index))]])
    M_ss_red = M_ss[0:len(chemodynamic_index)-1,:]
    M = nsimplify(M_ss_red.col_join(M_G))
    # Solve the linear equations
    q_cd_ss =  nsimplify(M.LUsolve(b))
    M_v = nsimplify(kappa*(B_f*N_cd_f.T-B_r*N_cd_r.T)*K_cd)
    v = nsimplify(M_v*q_cd_ss)
    v_ss = factor(v[0]) # This is where the performance issue comes from
    # Get the numerator and denominator of the steady state equation
    vss_num, vss_den = fraction(v_ss)
    return vss_num, vss_den
    # Simplify the steady state equation
def simplify_flux_ss(vss_num,vss_den):
    # Get the subexpression of vss_num containing q, E and exp(F*V_m/(R*T))
    vss_num_terms = Add.make_args(expand(vss_num))
    vss_num_subterms =[]
    Q={}
    for i in range(len(vss_num_terms)):
        qsubliterals=[j for j in vss_num_terms[i].atoms() if (str(j).startswith('q') or j==E)]
        for qi in qsubliterals:
            Q.update({qi:(qi,'fmol')})
        if vss_num_terms[i].has(exp(F*V_m/(R*T))): qsubliterals.append(exp(F*V_m/(R*T)))
        if len(qsubliterals)>1:
            vss_num_subterms.append(Mul(*qsubliterals))
        elif len(qsubliterals)==1:
            vss_num_subterms.append(qsubliterals[0])
    # Get the subexpression of vss_den containing q and exp(F*V_m/(R*T))
    vss_den_terms = Add.make_args(expand(vss_den))
    vss_den_subterms =[]
    for i in range(len(vss_den_terms)):
        subliterals=[j for j in vss_den_terms[i].atoms() if str(j).startswith('q')]
        if vss_den_terms[i].has(exp(F*V_m/(R*T))): subliterals.append(exp(F*V_m/(R*T)))
        if len(subliterals)>1:
            vss_den_subterms.append(Mul(*subliterals))
        elif len(subliterals)==1:
            vss_den_subterms.append(subliterals[0])
    
    def join_unit (expri):
        symbols_expri = expri.atoms(Symbol)
        unit_list =[]
        first_unit=[]
        for s in symbols_expri:
           power_s = Poly(expri,s).monoms()
           if power_s[0][0] == 1:
               first_unit.append(f'{s.name}')
           else:
               unit_list.append(f'{s.name}{power_s[0][0]}')
        unit_list = first_unit + unit_list
        unit_expr = '_'.join(unit_list)

        return unit_expr
    # Get the units of the parameters P
    def get_Units(terms):
        first_term = Add.make_args(terms)[0]
        Units_list=[]
        Ks_units=[1/Symbol('fmol') for j in first_term.atoms() if str(j).startswith('K')]
        kappas_units=[Symbol('fmol')/Symbol('sec') for j in first_term.atoms() if str(j).startswith('kappa')]
        E_units = [Symbol('fmol') for j in first_term.atoms() if j==E]
        if len(Ks_units)>0:
            Units_list=Units_list+Ks_units
        if len(kappas_units)>0:
            Units_list=Units_list+kappas_units
        if len(E_units)>0:
            Units_list=Units_list+E_units

        iUnits =  Mul(*Units_list) 
        # if iUnits is number: return dimensionless
        if iUnits.is_number: return 'dimensionless'
        else: 
            Units_num, Units_den=fraction(iUnits)
        if Units_num .is_number: # join the items in Units_den with '_'
            cellml_units_den = join_unit (Units_den) 
            cellml_units = f'per_{cellml_units_den}'
        else:
            cellml_units_num = join_unit (Units_num)
            cellml_units_den = join_unit (Units_den)
            cellml_units = f'{cellml_units_num}_per_{cellml_units_den}'

        return cellml_units    
    
    # Collect the terms of the numerator and denominator to simplify the expression
    P={}
    dict_vss_num= collect(expand(vss_num),vss_num_subterms, evaluate=False)
    dict_vss_num_keys = list(dict_vss_num.keys())
    sub_dict = {}
    for i,key in enumerate(dict_vss_num_keys):
        if dict_vss_num[key].could_extract_minus_sign():
            sub_dict.update({-dict_vss_num[key]:Symbol(f'P_{i}')})
            P.update({Symbol(f'P_{i}'):(-dict_vss_num[key],get_Units(dict_vss_num[key]))})
        else:
            sub_dict.update({dict_vss_num[key]:Symbol(f'P_{i}')})
            P.update({Symbol(f'P_{i}'):(dict_vss_num[key],get_Units(dict_vss_num[key]))})

    c_vss_num = collect(expand(vss_num),vss_num_subterms)
    c_vss_num_simp= factor( (c_vss_num).subs(sub_dict))
    print('c_vss_num_sim=\n',c_vss_num_simp)

    dict_vss_den= collect(expand(vss_den),vss_den_subterms, evaluate=False)
    dict_vss_den_keys = list(dict_vss_den.keys())
    sub_dict = {}
    for j,key in enumerate(dict_vss_den_keys):
        if dict_vss_den[key].could_extract_minus_sign():
            sub_dict.update({-dict_vss_den[key]:Symbol(f'P_{i+j+1}')})
            P.update({Symbol(f'P_{i+j+1}'):(-dict_vss_den[key],get_Units(dict_vss_den[key]))})
        else:
            sub_dict.update({dict_vss_den[key]:Symbol(f'P_{i+j+1}')})
            P.update({Symbol(f'P_{i+j+1}'):(dict_vss_den[key],get_Units(dict_vss_den[key]))})

    c_vss_den= collect(expand(vss_den),vss_den_subterms)
    c_vss_den_simp= (c_vss_den).subs(sub_dict)
    print('c_vss_den_sim=\n',c_vss_den_simp)
    v_ss_simplified = c_vss_num_simp/c_vss_den_simp
    print('v_ss_simplified=\n',v_ss_simplified)
    for key in P.keys():
        print(key,'=',P[key])
    return v_ss_simplified, P, Q
    
def flux_ss_diagram(CompName,CompType,ReName,ReType,N_f,N_r):
    # Based on the approach proposed in 
    # Hill, Terrell. Free energy transduction in biology: the steady-state kinetic and thermodynamic formalism. Elsevier, 2012.
    
    # convert the string stoichiometric matrix to float matrix   
    Nf = nsimplify(Matrix(np.array(N_f,dtype=float)))
    Nr = nsimplify(Matrix(np.array(N_r,dtype=float)))
    # Get the quantities q of the chemodynamic species (in the enzyme reaction network)
    q_cd = [f'q_{comp}' for i,comp in enumerate(CompName) if CompType[i]=='Ce']
    # Get the reaction rate constants kappa
    kappa = [Symbol(f'kappa_{re}') for re in ReName]
    # Construct a directed graph of the reaction network
    # Compute the apparent reaction rate constants of the enzyme reaction network
    G = nx.DiGraph()
    for i,comp in enumerate(CompName):
        if CompType[i]=='Ce':
            G.add_node(comp)  
    for j,re in enumerate(ReName):
        k_f_terms =[]
        k_r_terms =[]
        for i,comp in enumerate(CompName):
            if Nf[i,j]!=0 and CompType[i]=='Ce':
                mu_f = R*T*log(Symbol(f'K_{comp}')*Symbol(f'q_{comp}'))
                q_f = Symbol(f'q_{comp}')
            elif Nf[i,j]!=0 and CompType[i]=='Se':
                mu_f = R*T*log(Symbol(f'K_{comp}')*Symbol(f'q_{comp}'))
            elif Nf[i,j]!=0 and CompType[i]=='Ve':
                mu_f = F*V_m
            else:
                mu_f = 0
            if mu_f != 0:
               k_f_terms.append(Nf[i,j]*mu_f)
            if Nr[i,j]!=0 and CompType[i]=='Ce':
                mu_r = R*T*log(Symbol(f'K_{comp}')*Symbol(f'q_{comp}'))
                q_r = Symbol(f'q_{comp}')
            elif Nr[i,j]!=0 and CompType[i]=='Se':
                mu_r = R*T*log(Symbol(f'K_{comp}')*Symbol(f'q_{comp}'))
            elif Nr[i,j]!=0 and CompType[i]=='Ve':
                mu_r = F*V_m
            else:
                mu_r = 0
            if mu_r != 0:
               k_r_terms.append(Nr[i,j]*mu_r)
        k_f_mat = Matrix(k_f_terms)
        k_r_mat = Matrix(k_r_terms)
        kf_exp = nsimplify(kappa[j]*exp(sum((k_f_mat)/(R*T))))
        dict_kf= collect(kf_exp,q_f, evaluate=False)
        kr_exp = nsimplify(kappa[j]*exp(sum((k_r_mat)/(R*T))))
        dict_kr= collect(kr_exp,q_r, evaluate=False)
        G.add_edge(q_f.name,q_r.name,reaction=re, k_f=dict_kf[list(dict_kf.keys())[0]], k_r=dict_kr[list(dict_kr.keys())[0]])
    
    edge_list = list(G.edges(data=True))
    
    # Construct a 2D sympy matrix to store the product of the rate constants on the edges
    # the first dimension is the number of q_cd, the second dimension is the number of edges (reactions)
    k_mat = Matrix([[0 for i in range(len(edge_list))] for j in range(len(q_cd))])
    for  j, edgej in enumerate (edge_list):
        G_copy = G.copy()
        G_copy.remove_edge(edgej[0],edgej[1]) # Partial diagram
        for i, q in enumerate (q_cd):
            item = []
            # Get the edge list that connects the node q in the reverse direction
            edge_list_q = list(nx.edge_dfs(G_copy,q,orientation='ignore'))
            edge_list_q_rev=[edge for edge in edge_list_q if edge[2]=='reverse']
            for edge in edge_list_q_rev:
                item.append(G_copy.get_edge_data(edge[0],edge[1])['k_f'])                          
            # Get the edge list that connects the node q in the forward direction
            edge_list_q_fwd = [edge for edge in edge_list_q if edge[2]=='forward']
            for edge in edge_list_q_fwd:
                item.append(G_copy.get_edge_data(edge[0],edge[1])['k_r'])
            # Get the product of all the k_f/k_r on the path reaching q
            k_mat[i,j] = prod(item)
    # Add the columns of the k_mat to get the steady state expression of q
    q_ss_E = Matrix([0 for i in range(len(q_cd))])
    for i in range(len(q_cd)):
        q_ss_E[i] = sum(k_mat[i,:])
    
    kf_all,kr_all = [],[]
    for  j, edgej in enumerate (edge_list):
        kf_all.append(G.get_edge_data(edgej[0],edgej[1])['k_f'])
        kr_all.append(G.get_edge_data(edgej[0],edgej[1])['k_r'])

    vss_num = factor(E*(prod(kf_all)-prod(kr_all)))
    vss_den= sum(q_ss_E[:])
    return vss_num,vss_den
                    
# main function
if __name__ == "__main__":
    # Get the csv file from the user by opening a file dialog
    read_csvBG()





