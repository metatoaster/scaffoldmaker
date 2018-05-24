"""
Generates a 3-D heart ventricles with base plane model, ready to attach the
atria, mitral and tricuspid valves, with LV + RV outlets ready to attach aorta and
pulmonary trunk and their valves regions.
"""

from __future__ import division
import math
from scaffoldmaker.meshtypes.meshtype_3d_heartventricles2 import MeshType_3d_heartventricles2
from scaffoldmaker.utils.eft_utils import *
from scaffoldmaker.utils.geometry import *
from scaffoldmaker.utils.interpolation import *
from scaffoldmaker.utils.zinc_utils import *
from scaffoldmaker.utils.eftfactory_tricubichermite import eftfactory_tricubichermite
from scaffoldmaker.utils.meshrefinement import MeshRefinement
import scaffoldmaker.utils.vector as vector
from opencmiss.zinc.element import Element, Elementbasis
from opencmiss.zinc.field import Field
from opencmiss.zinc.node import Node

class MeshType_3d_heartventriclesbase2(object):
    '''
    classdocs
    '''
    @staticmethod
    def getName():
        return '3D Heart Ventricles with Base 2'

    @staticmethod
    def getDefaultOptions():
        options = MeshType_3d_heartventricles2.getDefaultOptions()
        # only works with particular numbers of elements around
        options['Number of elements around LV free wall'] = 5
        options['Number of elements around septum'] = 6
        # works best with particular numbers of elements up
        options['Number of elements up apex'] = 1
        options['Number of elements up septum'] = 4
        # additional options
        options['Number of elements around atria'] = 7
        options['Atrial septum thickness'] = 0.06
        options['Atria major axis rotation degrees'] = 40.0
        options['Base height'] = 0.1
        options['Base thickness'] = 0.06
        options['LV outlet inner diameter'] = 0.3
        options['LV outlet wall thickness'] = 0.02
        options['RV outlet inner diameter'] = 0.3
        options['RV outlet wall thickness'] = 0.02
        options['Outlet element length'] = 0.1
        options['Outlet incline degrees'] = 15.0
        options['Outlet spacing'] = 0.04
        return options

    @staticmethod
    def getOrderedOptionNames():
        optionNames = MeshType_3d_heartventricles2.getOrderedOptionNames()
        optionNames.insert(4, 'Number of elements around atria')
        optionNames += [
            'Atrial septum thickness',
            'Atria major axis rotation degrees',
            'Base height',
            'Base thickness',
            'LV outlet inner diameter',
            'LV outlet wall thickness',
            'RV outlet inner diameter',
            'RV outlet wall thickness',
            'Outlet element length',
            'Outlet incline degrees',
            'Outlet spacing']
        # want refinement options last
        for optionName in [
            'Refine',
            'Refine number of elements surface',
            'Refine number of elements through LV wall',
            'Refine number of elements through RV wall']:
            optionNames.remove(optionName)
            optionNames.append(optionName)
        return optionNames

    @staticmethod
    def checkOptions(options):
        MeshType_3d_heartventricles2.checkOptions(options)
        # only works with particular numbers of elements around
        #options['Number of elements around LV free wall'] = 5
        #options['Number of elements around septum'] = 6
        if options['Number of elements around atria'] < 6:
            options['Number of elements around atria'] = 6
        for key in [
            'Atrial septum thickness',
            'Base height',
            'Base thickness',
            'LV outlet inner diameter',
            'LV outlet wall thickness',
            'RV outlet inner diameter',
            'RV outlet wall thickness',
            'Outlet element length',
            'Outlet spacing']:
            if options[key] < 0.0:
                options[key] = 0.0
        if options['Atria major axis rotation degrees'] < -75.0:
            options['Atria major axis rotation degrees'] = -75.0
        elif options['Atria major axis rotation degrees'] > 75.0:
            options['Atria major axis rotation degrees'] = 75.0
        # need even number of refine surface elements for elements with hanging nodes to conform
        if (options['Refine number of elements surface'] % 2) == 1:
            options['Refine number of elements surface'] += 1

    @staticmethod
    def generateBaseMesh(region, options):
        """
        Generate the base tricubic Hermite mesh. See also generateMesh().
        :param region: Zinc region to define model in. Must be empty.
        :param options: Dict containing options. See getDefaultOptions().
        :return: None
        """
        elementsCountAroundLVFreeWall = options['Number of elements around LV free wall']
        elementsCountAroundSeptum = options['Number of elements around septum']
        elementsCountAroundLV = elementsCountAroundLVFreeWall + elementsCountAroundSeptum
        elementsCountUpApex = options['Number of elements up apex']
        elementsCountUpSeptum = options['Number of elements up septum']
        elementsCountUpLV = elementsCountUpApex + elementsCountUpSeptum
        elementsCountUpRV = elementsCountUpSeptum + 1
        elementsCountAroundRV = elementsCountAroundSeptum + 2
        elementsCountAtrialSeptum = 2  # elementsCountAroundSeptum - 5
        elementsCountAroundAtria = options['Number of elements around atria']
        totalHeight = options['Total height']
        lvOuterRadius = options['LV outer radius']
        lvFreeWallThickness = options['LV free wall thickness']
        lvApexThickness = options['LV apex thickness']
        rvHeight = options['RV height']
        rvArcAroundRadians = math.radians(options['RV arc around degrees'])
        rvFreeWallThickness = options['RV free wall thickness']
        rvWidth = options['RV width']
        rvExtraCrossRadiusBase = options['RV extra cross radius base']
        vSeptumThickness = options['Ventricular septum thickness']
        vSeptumBaseRadialDisplacement = options['Ventricular septum base radial displacement']
        useCrossDerivatives = options['Use cross derivatives']
        aMajorAxisRadians = math.radians(options['Atria major axis rotation degrees'])
        aSeptumThickness = options['Atrial septum thickness']
        baseHeight = options['Base height']
        baseThickness = options['Base thickness']
        lvOutletInnerRadius = options['LV outlet inner diameter']*0.5
        lvOutletWallThickness = options['LV outlet wall thickness']
        lvOutletOuterRadius = lvOutletInnerRadius + lvOutletWallThickness
        rvOutletInnerRadius = options['RV outlet inner diameter']*0.5
        rvOutletWallThickness = options['RV outlet wall thickness']
        rvOutletOuterRadius = rvOutletInnerRadius + rvOutletWallThickness
        outletElementLength = options['Outlet element length']
        outletInclineRadians = math.radians(options['Outlet incline degrees'])
        outletSpacing = options['Outlet spacing']

        # generate heartventricles2 model to add base plane to
        MeshType_3d_heartventricles2.generateBaseMesh(region, options)

        fm = region.getFieldmodule()
        fm.beginChange()
        coordinates = getOrCreateCoordinateField(fm)
        cache = fm.createFieldcache()

        #################
        # Create nodes
        #################

        nodes = fm.findNodesetByFieldDomainType(Field.DOMAIN_TYPE_NODES)
        nodetemplate = nodes.createNodetemplate()
        nodetemplate.defineField(coordinates)
        nodetemplate.setValueNumberOfVersions(coordinates, -1, Node.VALUE_LABEL_VALUE, 1)
        nodetemplate.setValueNumberOfVersions(coordinates, -1, Node.VALUE_LABEL_D_DS1, 1)
        nodetemplate.setValueNumberOfVersions(coordinates, -1, Node.VALUE_LABEL_D_DS2, 1)
        nodetemplate.setValueNumberOfVersions(coordinates, -1, Node.VALUE_LABEL_D_DS3, 1)
        # nodes used only in bicubic-linear elements do not have D_DS3 parameters
        nodetemplateLinearS3 = nodes.createNodetemplate()
        nodetemplateLinearS3.defineField(coordinates)
        nodetemplateLinearS3.setValueNumberOfVersions(coordinates, -1, Node.VALUE_LABEL_VALUE, 1)
        nodetemplateLinearS3.setValueNumberOfVersions(coordinates, -1, Node.VALUE_LABEL_D_DS1, 1)
        nodetemplateLinearS3.setValueNumberOfVersions(coordinates, -1, Node.VALUE_LABEL_D_DS2, 1)

        nodeIdentifier = startNodeIdentifier = getMaximumNodeIdentifier(nodes) + 1

        # node offsets for row, wall in LV, plus first LV node on inside top
        norl = elementsCountAroundLV
        nowl = 1 + elementsCountUpLV*norl
        nidl = nowl - norl + 1
        # node offsets for row, wall in RV, plus first RV node on inside top
        norr = elementsCountAroundRV - 1
        nowr = elementsCountUpRV*norr
        nidr = nowl*2 + 1 + nowr - norr
        #print('nidl',nidl,'nidr',nidr)

        # LV outlet
        elementsCountAroundOutlet = 6
        # GRC Set properly:
        defaultOutletScale3 = 0.5
        nidca = nidl + nowl + elementsCountAroundSeptum - 1
        nidcb = nidr + elementsCountAroundSeptum - 1
        #print('px nodes', nidca, nidcb)
        cache.setNode(nodes.findNodeByIdentifier(nidca))
        result, pxa = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, 3)
        cache.setNode(nodes.findNodeByIdentifier(nidcb))
        result, pxb = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, 3)
        px = [ 0.5*(pxa[c] + pxb[c]) for c in range(3) ]
        node = nodes.findNodeByIdentifier(nidl)
        cache.setNode(node)
        result, ax = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, 3)
        node = nodes.findNodeByIdentifier(nidr)
        cache.setNode(node)
        result, bx = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, 3)
        bx = [ 0.5*(ax[i] + bx[i]) for i in range(2) ]
        bx.append(ax[2])
        ax = [ (bx[c] - px[c]) for c in range(3) ]
        ax = vector.normalise(ax)
        baseRotationRadians = math.atan2(ax[1], ax[0])
        # get crux location
        outletSpacingRadians = 0.25*math.pi  # GRC make option?
        outletSpacingHorizontal = outletSpacing*math.cos(outletSpacingRadians)
        outletSpacingVertical = outletSpacing*math.sin(outletSpacingRadians)
        cruxOffset = rvOutletOuterRadius + outletSpacingHorizontal + 2.0*lvOutletOuterRadius
        cx = [ (px[c] + ax[c]*cruxOffset) for c in range(3) ]

        #print('baseRotationRadians', baseRotationRadians)

        cosOutletInclineRadians = math.cos(outletInclineRadians)
        sinOutletInclineRadians = math.sin(outletInclineRadians)
        lvOutletCentre = [
            cx[0] - ax[0]*lvOutletOuterRadius,
            cx[1] - ax[1]*lvOutletOuterRadius,
            baseHeight + baseThickness + sinOutletInclineRadians*lvOutletOuterRadius ]

        radiansPerElementAroundOutlet = 2.0*math.pi/elementsCountAroundOutlet
        x = [ 0.0, 0.0, 0.0 ]
        dx_ds1 = [ 0.0, 0.0, 0.0 ]
        dx_ds3 = [ 0.0, 0.0, 0.0 ]
        lvOutletNodeId = []
        for n3 in range(2):
            radius = lvOutletInnerRadius if (n3 == 0) else lvOutletOuterRadius
            loAxis1 = [ radius*ax[c] for c in range(3) ]
            loAxis2 = [ -loAxis1[1]*cosOutletInclineRadians, loAxis1[0]*cosOutletInclineRadians, -radius*sinOutletInclineRadians ]
            loAxis3 = vector.crossproduct3(loAxis1, loAxis2)
            scale = outletElementLength/vector.magnitude(loAxis3)
            dx_ds2 = [ v*scale for v in loAxis3 ]
            outletNodeId = []
            for n1 in range(elementsCountAroundOutlet):
                radiansAround = n1*radiansPerElementAroundOutlet
                cosRadiansAround = math.cos(radiansAround)
                sinRadiansAround = math.sin(radiansAround)
                outletScale3 = outletSpacing/radius if (n1 == 3) else defaultOutletScale3
                for c in range(3):
                    x[c] = lvOutletCentre[c] + loAxis1[c]*cosRadiansAround + loAxis2[c]*sinRadiansAround
                    dx_ds1[c] = radiansPerElementAroundOutlet*(loAxis1[c]*-sinRadiansAround + loAxis2[c]*cosRadiansAround)
                node = nodes.createNode(nodeIdentifier, nodetemplateLinearS3 if (n3 == 0) else nodetemplate)
                outletNodeId.append(nodeIdentifier)
                cache.setNode(node)
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, x)
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS1, 1, dx_ds1)
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS2, 1, dx_ds2)
                if n3 == 1:
                    dx_ds3 = [ outletScale3*(loAxis1[c]*cosRadiansAround + loAxis2[c]*sinRadiansAround) for c in range(3) ]
                    if n1 in [ 2, 4 ]:
                        dx_ds3[2] = -dx_ds3[2]
                        scale = radiansPerElementAroundOutlet*rvOutletOuterRadius/vector.magnitude(dx_ds3)
                        dx_ds3 = [ d*scale for d in dx_ds3 ]
                    coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, dx_ds3)
                    if n1 == 0:
                        cruxCentreNodeId = nodeIdentifier
                        cruxCentre = [ x[0], x[1], x[2] ]
                    elif n1 == 1:
                        cruxRightNodeId = nodeIdentifier
                        cruxRight = [ x[0], x[1], x[2] ]
                    elif n1 == (elementsCountAroundOutlet - 1):
                        cruxLeftNodeId = nodeIdentifier
                        cruxLeft = [ x[0], x[1], x[2] ]
                    elif n1 == 3:
                        lvOutletOuterSpaceX = [ x[0], x[1], x[2] ]
                nodeIdentifier += 1
            lvOutletNodeId.append(outletNodeId)

        # RV outlet - for bicubic-linear tube connection
        outletCentreSpacing = lvOutletOuterRadius + outletSpacingHorizontal + rvOutletOuterRadius
        rvOutletCentre = [ (lvOutletCentre[c] - outletCentreSpacing*ax[c]) for c in range(3) ]
        # add outletSpacingVertical rotated by outletInclineRadians
        unitCrossX = vector.normalise([-ax[1], ax[0]])
        rvOutletCentre[0] -= outletSpacingVertical*sinOutletInclineRadians*unitCrossX[0]
        rvOutletCentre[1] -= outletSpacingVertical*sinOutletInclineRadians*unitCrossX[1]
        rvOutletCentre[2] += outletSpacingVertical*cosOutletInclineRadians

        rvOutletNodeId = []
        for n3 in range(2):
            radius = rvOutletInnerRadius if (n3 == 0) else rvOutletOuterRadius
            roAxis1 = [ radius*ax[c] for c in range(3) ]
            roAxis2 = [ -roAxis1[1]*cosOutletInclineRadians, roAxis1[0]*cosOutletInclineRadians, radius*sinOutletInclineRadians ]
            roAxis3 = vector.crossproduct3(roAxis1, roAxis2)
            scale = outletElementLength/vector.magnitude(roAxis3)
            dx_ds2 = [ v*scale for v in roAxis3 ]
            outletNodeId = []
            for n1 in range(elementsCountAroundOutlet):
                radiansAround = n1*radiansPerElementAroundOutlet
                cosRadiansAround = math.cos(radiansAround)
                sinRadiansAround = math.sin(radiansAround)
                outletScale3 = outletSpacing/radius if (n1 == 0) else defaultOutletScale3
                for c in range(3):
                    x[c] = rvOutletCentre[c] + roAxis1[c]*cosRadiansAround + roAxis2[c]*sinRadiansAround
                    dx_ds1[c] = radiansPerElementAroundOutlet*(roAxis1[c]*-sinRadiansAround + roAxis2[c]*cosRadiansAround)
                node = nodes.createNode(nodeIdentifier, nodetemplateLinearS3 if (n3 == 0) else nodetemplate)
                outletNodeId.append(nodeIdentifier)
                cache.setNode(node)
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, x)
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS1, 1, dx_ds1)
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS2, 1, dx_ds2)
                if n3 == 1:
                    dx_ds3 = [ outletScale3*(roAxis1[c]*cosRadiansAround + roAxis2[c]*sinRadiansAround) for c in range(3) ]
                    if n1 in [ 1, 5 ]:
                        dx_ds3[2] = -dx_ds3[2]
                        scale = radiansPerElementAroundOutlet*rvOutletOuterRadius/vector.magnitude(dx_ds3)
                        dx_ds3 = [ d*scale for d in dx_ds3 ]
                    coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, dx_ds3)
                    if n1 == 0:
                        rvOutletOuterSpaceX = [ x[0], x[1], x[2] ]
                nodeIdentifier += 1
            rvOutletNodeId.append(outletNodeId)

        # fix derivative 3 between lv, rv outlets
        cache.setNode(nodes.findNodeByIdentifier(lvOutletNodeId[1][3]))
        dx_ds3 = [ (rvOutletOuterSpaceX[c] - lvOutletOuterSpaceX[c]) for c in range(3)]
        coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, dx_ds3)
        cache.setNode(nodes.findNodeByIdentifier(rvOutletNodeId[1][0]))
        coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, [ -d for d in dx_ds3])

        # Atria nodes

        #print('\nelementsCountAroundAtria = ',elementsCountAroundAtria)
        # GRC parameter?
        atriumInletSlopeRadians = math.pi/6.0
        # GRC change rvFreeWallThickness to new parameter?
        atriumInletSlopeLength = rvFreeWallThickness
        atriumInletSlopeHeight = rvFreeWallThickness*math.tan(atriumInletSlopeRadians)

        # GRC revisit:
        aInnerMajorMag = 0.8*(lvOuterRadius - lvFreeWallThickness - 0.5*vSeptumBaseRadialDisplacement)
        aInnerMinorMag = 1.0*(lvOuterRadius - lvFreeWallThickness - lvOutletOuterRadius)
        #print('inner mag major', aInnerMajorMag, 'minor', aInnerMinorMag)
        aOuterMajorMag = aInnerMajorMag + atriumInletSlopeLength
        aOuterMinorMag = aInnerMinorMag + atriumInletSlopeLength
        #print('outer mag major', aOuterMajorMag, 'minor', aOuterMinorMag)

        laMajorAxisRadians = baseRotationRadians + 0.5*math.pi - aMajorAxisRadians
        laInnerMajor = [  aInnerMajorMag*math.cos(laMajorAxisRadians), aInnerMajorMag*math.sin(laMajorAxisRadians), 0.0 ]
        laInnerMinor = [ -aInnerMinorMag*math.sin(laMajorAxisRadians), aInnerMinorMag*math.cos(laMajorAxisRadians), 0.0 ]
        laOuterMajor = [  aOuterMajorMag*math.cos(laMajorAxisRadians), aOuterMajorMag*math.sin(laMajorAxisRadians), 0.0 ]
        laOuterMinor = [ -aOuterMinorMag*math.sin(laMajorAxisRadians), aOuterMinorMag*math.cos(laMajorAxisRadians), 0.0 ]

        raMajorAxisRadians = baseRotationRadians - 0.5*math.pi + aMajorAxisRadians
        raInnerMajor = [  aInnerMajorMag*math.cos(raMajorAxisRadians), aInnerMajorMag*math.sin(raMajorAxisRadians), 0.0 ]
        raInnerMinor = [ -aInnerMinorMag*math.sin(raMajorAxisRadians), aInnerMinorMag*math.cos(raMajorAxisRadians), 0.0 ]
        raOuterMajor = [  aOuterMajorMag*math.cos(raMajorAxisRadians), aOuterMajorMag*math.sin(raMajorAxisRadians), 0.0 ]
        raOuterMinor = [ -aOuterMinorMag*math.sin(raMajorAxisRadians), aOuterMinorMag*math.cos(raMajorAxisRadians), 0.0 ]

        # get la angle intersecting with cruxLeft, thence laCentre

        rotRadians = baseRotationRadians + 0.5*math.pi
        cosRotRadians = math.cos(rotRadians)
        sinRotRadians = math.sin(rotRadians)
        cruxLeftModX = (cruxLeft[0] - cruxCentre[0])*cosRotRadians + (cruxLeft[1] - cruxCentre[1])*sinRotRadians
        cruxLeftModY = (cruxLeft[0] - cruxCentre[0])*-sinRotRadians + (cruxLeft[1] - cruxCentre[1])*cosRotRadians

        axInnerMod = aInnerMajorMag*math.cos(aMajorAxisRadians)
        bxInnerMod = aInnerMinorMag*math.sin(aMajorAxisRadians)
        #print('Inner axMod', axInnerMod, 'bxMod', bxInnerMod)
        laSeptumRadians = math.atan2(bxInnerMod, axInnerMod)
        #print('laSeptumRadians', laSeptumRadians)
        raSeptumRadians = -laSeptumRadians
        laCentreModX = -0.5*aSeptumThickness - axInnerMod*math.cos(laSeptumRadians) - bxInnerMod*math.sin(laSeptumRadians)

        axMod = aOuterMajorMag*math.cos(aMajorAxisRadians)
        ayMod = aOuterMajorMag*-math.sin(aMajorAxisRadians)
        bxMod = aOuterMinorMag*math.sin(aMajorAxisRadians)
        byMod = aOuterMinorMag*math.cos(aMajorAxisRadians)
        #print('Outer axMod', axMod, 'bxMod', bxMod)

        dX = cruxLeftModX - laCentreModX
        #print('laCentreModX', laCentreModX, 'cruxLeftModX', cruxLeftModX, 'dX', dX)
        # iterate with Newton's method to get laCruxLeftRadians
        laCruxLeftRadians = math.pi*0.5
        iters = 0
        fTol = aOuterMajorMag*1.0E-10
        while True:
            cosAngle = math.cos(laCruxLeftRadians)
            sinAngle = math.sin(laCruxLeftRadians)
            f = axMod*cosAngle + bxMod*sinAngle - dX
            if math.fabs(f) < fTol:
                break;
            df = -axMod*sinAngle + bxMod*cosAngle
            #print(iters, '. theta', laCruxLeftRadians, 'f', f,'df',df,'-->',laCruxLeftRadians - f/df)
            laCruxLeftRadians -= f/df
            iters += 1
            if iters == 100:
                print('No convergence!')
                break
        #print(iters,'iters : laCruxLeftRadians', laCruxLeftRadians)
        laCentreModY = cruxLeftModY - ayMod*math.cos(laCruxLeftRadians) - byMod*math.sin(laCruxLeftRadians)

        #print('laCentreMod', laCentreModX, laCentreModY)
        laCentreX = cruxCentre[0] + laCentreModX*cosRotRadians + laCentreModY*-sinRotRadians
        laCentreY = cruxCentre[1] + laCentreModX*sinRotRadians + laCentreModY*cosRotRadians

        raCruxLeftRadians = -laCruxLeftRadians
        raCentreX = cruxCentre[0] - laCentreModX*cosRotRadians + laCentreModY*-sinRotRadians
        raCentreY = cruxCentre[1] - laCentreModX*sinRotRadians + laCentreModY*cosRotRadians

        aCentreOuterZ = cruxRight[2]
        aCentreInnerZ = cruxRight[2] - atriumInletSlopeHeight
        #aCentreOuterZ = cruxCentre[2]
        #aCentreInnerZ = aCentreOuterZ - atriumInletSlopeHeight
        #if aCentreInnerZ > cruxRight[2]:
        #    aCentreInnerZ == cruxRight[2]

        atrialPerimeterLength = getApproximateEllipsePerimeter(aOuterMajorMag, aOuterMinorMag)
        atrialSeptumCentreToCruxLeftLength = getEllipseArcLength(aOuterMajorMag, aOuterMinorMag, laSeptumRadians, laCruxLeftRadians)
        atrialSeptumElementLength = atrialSeptumCentreToCruxLeftLength/(1.0 + elementsCountAtrialSeptum*0.5)
        atrialFreeWallElementLength = (atrialPerimeterLength - atrialSeptumElementLength*(elementsCountAtrialSeptum + 2)) \
            / (elementsCountAroundAtria - elementsCountAtrialSeptum - 2)
        atrialTransitionElementLength = 0.5*(atrialSeptumElementLength + atrialFreeWallElementLength)

        #print('lengths septum', atrialSeptumElementLength, 'transition', atrialTransitionElementLength, 'freewall', atrialFreeWallElementLength)
        #print('total length', atrialSeptumElementLength*(elementsCountAtrialSeptum + 1) + 2*atrialTransitionElementLength \
        #    + (elementsCountAroundAtria - elementsCountAtrialSeptum - 3)*atrialFreeWallElementLength, 'vs.', atrialPerimeterLength)

        laRadians = []
        laOuterDerivatives = []
        radiansAround = laSeptumRadians
        if (elementsCountAtrialSeptum % 2) == 1:
            radiansAround = updateEllipseAngleByArcLength(aOuterMajorMag, aOuterMinorMag, radiansAround, 0.5*atrialSeptumElementLength)
        outerDerivative = atrialSeptumElementLength
        lan1CruxLimit = elementsCountAtrialSeptum//2 + 1
        lan1SeptumLimit = elementsCountAroundAtria - (elementsCountAtrialSeptum + 1)//2 - 1
        #print('lan1CruxLimit', lan1CruxLimit, 'lan1SeptumLimit', lan1SeptumLimit)
        for n1 in range(elementsCountAroundAtria):
            laRadians.append(radiansAround)
            laOuterDerivatives.append(outerDerivative)
            if (n1 < lan1CruxLimit) or (n1 > lan1SeptumLimit):
                elementLength = atrialSeptumElementLength
                outerDerivative = atrialSeptumElementLength
            elif n1 == lan1CruxLimit:
                elementLength = atrialTransitionElementLength
                outerDerivative = atrialFreeWallElementLength
            elif n1 == lan1SeptumLimit:
                elementLength = atrialTransitionElementLength
                outerDerivative = atrialSeptumElementLength
            else:
                elementLength = atrialFreeWallElementLength
                outerDerivative = atrialFreeWallElementLength
            #print(n1,': elementLength', elementLength, 'outerDerivative', outerDerivative)
            radiansAround = updateEllipseAngleByArcLength(aOuterMajorMag, aOuterMinorMag, radiansAround, elementLength)
        laInnerDerivatives = []
        finalArcLength = prevArcLength = getEllipseArcLength(aInnerMajorMag, aInnerMinorMag, laRadians[-1] - 2.0*math.pi, laRadians[0])
        for n1 in range(elementsCountAroundAtria):
            if n1 == (elementsCountAroundAtria - 1):
                nextArcLength = finalArcLength
            else:
                nextArcLength = getEllipseArcLength(aInnerMajorMag, aInnerMinorMag, laRadians[n1], laRadians[n1 + 1])
            if laOuterDerivatives[n1] is atrialSeptumElementLength:
                arcLength = min(prevArcLength, nextArcLength)
            else:
                arcLength = max(prevArcLength, nextArcLength)
            laInnerDerivatives.append(arcLength)
            prevArcLength = nextArcLength

        #print('raRadians', laRadians)
        #print('laOuterDerivatives', laOuterDerivatives)
        #print('laInnerDerivatives', laInnerDerivatives)

        raRadians = []
        raInnerDerivatives = []
        raOuterDerivatives = []
        for n1 in range(elementsCountAroundAtria):
            raRadians.append(2.0*math.pi - laRadians[-n1])
            raInnerDerivatives.append(laInnerDerivatives[-n1])
            raOuterDerivatives.append(laOuterDerivatives[-n1])
        # fix first one so not out by 2pi
        raRadians[0] = raSeptumRadians

        laNodeId = [ [-1]*elementsCountAroundAtria, [-1]*elementsCountAroundAtria ]

        for n3 in range(2):
            for n1 in range(elementsCountAroundAtria):
                radiansAround = laRadians[n1]
                cosRadiansAround = math.cos(radiansAround)
                sinRadiansAround = math.sin(radiansAround)
                inner = [
                    laCentreX + cosRadiansAround*laInnerMajor[0] + sinRadiansAround*laInnerMinor[0],
                    laCentreY + cosRadiansAround*laInnerMajor[1] + sinRadiansAround*laInnerMinor[1],
                    aCentreInnerZ ]
                outer = [
                    laCentreX + cosRadiansAround*laOuterMajor[0] + sinRadiansAround*laOuterMinor[0],
                    laCentreY + cosRadiansAround*laOuterMajor[1] + sinRadiansAround*laOuterMinor[1],
                    aCentreOuterZ ]

                if (n3 == 1) and ((n1 <= lan1CruxLimit) or (n1 > (lan1SeptumLimit + 2))):
                    continue  # already have a node from crux or will get from right atrial septum
                node = nodes.createNode(nodeIdentifier, nodetemplate)
                laNodeId[n3][n1] = nodeIdentifier
                cache.setNode(node)
                result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, inner if (n3 == 0) else outer)
                if n3 == 0:
                    dx_ds1 = [
                        -sinRadiansAround*laInnerMajor[0] + cosRadiansAround*laInnerMinor[0],
                        -sinRadiansAround*laInnerMajor[1] + cosRadiansAround*laInnerMinor[1],
                        0.0 ]
                    scale1 = laInnerDerivatives[n1]
                else:
                    dx_ds1 = [
                        -sinRadiansAround*laOuterMajor[0] + cosRadiansAround*laOuterMinor[0],
                        -sinRadiansAround*laOuterMajor[1] + cosRadiansAround*laOuterMinor[1],
                        0.0 ]
                    scale1 = laOuterDerivatives[n1]
                scale1 /= vector.magnitude(dx_ds1)
                dx_ds1 = [ d*scale1 for d in dx_ds1 ]
                dx_ds3 = [ outer[0] - inner[0], outer[1] - inner[1], outer[2] - inner[2] ]
                if (n1 < lan1CruxLimit) or (n1 > lan1SeptumLimit):
                    dx_ds2 = [ 0.0, 0.0, aCentreInnerZ ]
                else:
                    dx_ds2 = [
                        dx_ds3[1]*dx_ds1[2] - dx_ds3[2]*dx_ds1[1],
                        dx_ds3[2]*dx_ds1[0] - dx_ds3[0]*dx_ds1[2],
                        dx_ds3[0]*dx_ds1[1] - dx_ds3[1]*dx_ds1[0] ]
                    # GRC check scaling here:
                    scale2 = inner[2]/vector.magnitude(dx_ds2)
                    dx_ds2 = [ d*scale2 for d in dx_ds2 ]
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS1, 1, dx_ds1)
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS2, 1, dx_ds2)
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, dx_ds3)
                nodeIdentifier += 1

        if False:
            # show axes of left atrium
            node = nodes.createNode(nodeIdentifier, nodetemplate)
            cache.setNode(node)
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, [ laCentreX, laCentreY, aCentreInnerZ ])
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS1, 1, [ laInnerMajor[0], laInnerMajor[1], 0.0 ])
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS2, 1, [ laInnerMinor[0], laInnerMinor[1], 0.0 ])
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, [ 0.0, 0.0, aCentreInnerZ ])
            nodeIdentifier += 1

            node = nodes.createNode(nodeIdentifier, nodetemplate)
            cache.setNode(node)
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, [ laCentreX, laCentreY, aCentreOuterZ ])
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS1, 1, [ laOuterMajor[0], laOuterMajor[1], 0.0 ])
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS2, 1, [ laOuterMinor[0], laOuterMinor[1], 0.0 ])
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, [ 0.0, 0.0, aCentreOuterZ ])
            nodeIdentifier += 1

        ran1SeptumLimit = elementsCountAtrialSeptum//2
        ran1CruxLimit = elementsCountAroundAtria - ran1SeptumLimit - 1
        raNodeId = [ [-1]*elementsCountAroundAtria, [-1]*elementsCountAroundAtria ]
        raNodeId[1][0] = laNodeId[0][0]
        raNodeId[1][-2] = lvOutletNodeId[1][1]
        raNodeId[1][-1] = lvOutletNodeId[1][0]

        for n3 in range(2):
            for n1 in range(elementsCountAroundAtria):
                radiansAround = raRadians[n1]
                cosRadiansAround = math.cos(radiansAround)
                sinRadiansAround = math.sin(radiansAround)
                inner = [
                    raCentreX + cosRadiansAround*raInnerMajor[0] + sinRadiansAround*raInnerMinor[0],
                    raCentreY + cosRadiansAround*raInnerMajor[1] + sinRadiansAround*raInnerMinor[1],
                    aCentreInnerZ ]
                outer = [
                    raCentreX + cosRadiansAround*raOuterMajor[0] + sinRadiansAround*raOuterMinor[0],
                    raCentreY + cosRadiansAround*raOuterMajor[1] + sinRadiansAround*raOuterMinor[1],
                    aCentreOuterZ ]

                if (n3 == 1) and ((n1 < ran1SeptumLimit) or (n1 >= ran1CruxLimit)):
                    continue  # already have a node from crux or will get from left atrial septum
                node = nodes.createNode(nodeIdentifier, nodetemplate)
                raNodeId[n3][n1] = nodeIdentifier
                cache.setNode(node)
                result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, inner if (n3 == 0) else outer)
                if n3 == 0:
                    dx_ds1 = [
                        -sinRadiansAround*raInnerMajor[0] + cosRadiansAround*raInnerMinor[0],
                        -sinRadiansAround*raInnerMajor[1] + cosRadiansAround*raInnerMinor[1],
                        0.0 ]
                    scale1 = raInnerDerivatives[n1]
                else:
                    dx_ds1 = [
                        -sinRadiansAround*raOuterMajor[0] + cosRadiansAround*raOuterMinor[0],
                        -sinRadiansAround*raOuterMajor[1] + cosRadiansAround*raOuterMinor[1],
                        0.0 ]
                    scale1 = raOuterDerivatives[n1]
                scale1 /= vector.magnitude(dx_ds1)
                dx_ds1 = [ d*scale1 for d in dx_ds1 ]
                dx_ds3 = [ outer[0] - inner[0], outer[1] - inner[1], outer[2] - inner[2] ]
                if (n1 <= ran1SeptumLimit) or (n1 > ran1CruxLimit):
                    dx_ds2 = [ 0.0, 0.0, aCentreInnerZ ]
                else:
                    dx_ds2 = [
                        dx_ds3[1]*dx_ds1[2] - dx_ds3[2]*dx_ds1[1],
                        dx_ds3[2]*dx_ds1[0] - dx_ds3[0]*dx_ds1[2],
                        dx_ds3[0]*dx_ds1[1] - dx_ds3[1]*dx_ds1[0] ]
                    if n1 == (ran1CruxLimit - 1):
                        # make derivative 2 on sv crest larger and less inclined
                        dx_ds2[2] *= 0.5 if (n3 == 0) else 0.25
                        mag2 = 1.5*(baseHeight + baseThickness)
                    else:
                        # GRC check scaling here:
                        mag2 = inner[2]
                    scale2 = mag2/vector.magnitude(dx_ds2)
                    dx_ds2 = [ d*scale2 for d in dx_ds2 ]
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS1, 1, dx_ds1)
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS2, 1, dx_ds2)
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, dx_ds3)
                nodeIdentifier += 1

        if False:
            # show axes of right atrium
            node = nodes.createNode(nodeIdentifier, nodetemplate)
            cache.setNode(node)
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, [ raCentreX, raCentreY, aCentreInnerZ ])
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS1, 1, [ raInnerMajor[0], raInnerMajor[1], 0.0 ])
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS2, 1, [ raInnerMinor[0], raInnerMinor[1], 0.0 ])
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, [ 0.0, 0.0, aCentreInnerZ ])
            nodeIdentifier += 1

            node = nodes.createNode(nodeIdentifier, nodetemplate)
            cache.setNode(node)
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, [ raCentreX, raCentreY, aCentreOuterZ ])
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS1, 1, [ raOuterMajor[0], raOuterMajor[1], 0.0 ])
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS2, 1, [ raOuterMinor[0], raOuterMinor[1], 0.0 ])
            result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, [ 0.0, 0.0, aCentreOuterZ ])
            nodeIdentifier += 1

        laNodeId[1][0] = raNodeId[0][0]
        laNodeId[1][1] = lvOutletNodeId[1][ 0]
        laNodeId[1][2] = lvOutletNodeId[1][-1]

        #print('laNodeId[0]', laNodeId[0])
        #print('laNodeId[1]', laNodeId[1])
        #print('raNodeId[0]', raNodeId[0])
        #print('raNodeId[1]', raNodeId[1])

        # compute dx_ds3 around atria from differences of nodes
        for i in range(2):
            aNodeId = laNodeId if (i == 0) else raNodeId
            for n1 in range(elementsCountAroundAtria):
                nid2 = aNodeId[1][n1]
                node2 = nodes.findNodeByIdentifier(nid2)
                cache.setNode(node2)
                result, x2 = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, 3 )
                nid1 = aNodeId[0][n1]
                node1 = nodes.findNodeByIdentifier(nid1)
                cache.setNode(node1)
                result, x1 = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, 3 )
                dx_ds3 = [ x2[0] - x1[0], x2[1] - x1[1], x2[2] - x1[2] ]
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, dx_ds3)
                if (i == 1) and ((n1 == 0) or (nid2 == cruxCentreNodeId)):
                    continue
                if nid2 in [ cruxLeftNodeId, cruxRightNodeId ]:
                    dx_ds3 = [ -d for d in dx_ds3 ]
                cache.setNode(node2)
                coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, dx_ds3)

        # fix crux centre dx_ds3:
        cache.setNode(nodes.findNodeByIdentifier(laNodeId[0][1]))
        result, x1 = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, 3 )
        cache.setNode(nodes.findNodeByIdentifier(raNodeId[0][-1]))
        result, x2 = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, 3 )
        cache.setNode(nodes.findNodeByIdentifier(cruxCentreNodeId))
        result, xc = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, 3 )
        d1 = [ (x1[c] - xc[c]) for c in range(3) ]
        d2 = [ (x2[c] - xc[c]) for c in range(3) ]
        dx_ds3 = [ d1[0] + d2[0], d1[1] + d2[1], 0.0 ]
        scale = vector.magnitude(d1)/vector.magnitude(dx_ds3)
        dx_ds3 = [ d*scale for d in dx_ds3 ]
        result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, dx_ds3 )

        # create nodes on bottom and top of supraventricular crest
        #print('sv crest interpolated from nodes', nidr + nowr + 4, lvOutletNodeId[1][2])
        node = nodes.findNodeByIdentifier(nidr + nowr + 4)
        cache.setNode(node)
        result, xa = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, 3 )
        result, d1a = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS1, 1, 3 )
        result, d2a = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS2, 1, 3 )
        node = nodes.findNodeByIdentifier(lvOutletNodeId[1][2])
        cache.setNode(node)
        result, xb = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, 3 )
        result, d1b = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS1, 1, 3 )
        result, d2b = coordinates.getNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, 3 )
        d2b = [ -2.0*d for d in d2b ]
        scale = 4.0*(baseHeight + baseThickness)/vector.magnitude(d2a)
        d2a = [ scale*d for d in d2a ]
        xi = 0.5
        x = list(interpolateCubicHermite(xa, d2a, xb, d2b, xi))
        dx_ds1 = [ 0.5*(d1a[c] + d1b[c]) for c in range(3) ]
        dx_ds2 = interpolateCubicHermiteDerivative(xa, d2a, xb, d2b, xi)
        dx_ds2 = [ 0.5*d for d in dx_ds2 ]
        radialVector = vector.normalise(vector.crossproduct3(dx_ds1, dx_ds2))
        dx_ds3 = [ baseThickness*d for d in radialVector ]

        x_inner = [ (x[c] - dx_ds3[c]) for c in range(3) ]
        curvatureScale = 1.0 - baseThickness*getCubicHermiteCurvature(xa, d2a, x, dx_ds2, radialVector, 1.0)
        dx_ds2_inner = [ curvatureScale*d for d in dx_ds2 ]

        node = nodes.createNode(nodeIdentifier, nodetemplate)
        cache.setNode(node)
        result = coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, x_inner)
        coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS1, 1, dx_ds1)
        coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS2, 1, dx_ds2_inner)
        coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, dx_ds3)
        crest_nid1 = nodeIdentifier
        nodeIdentifier += 1

        node = nodes.createNode(nodeIdentifier, nodetemplate)
        cache.setNode(node)
        coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, x)
        coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS1, 1, dx_ds1)
        coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS2, 1, dx_ds2)
        coordinates.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS3, 1, dx_ds3)
        crest_nid2 = nodeIdentifier
        nodeIdentifier += 1

        #################
        # Create elements
        #################

        mesh = fm.findMeshByDimension(3)
        tricubichermite = eftfactory_tricubichermite(mesh, useCrossDerivatives)
        eft = tricubichermite.createEftNoCrossDerivatives()

        elementIdentifier = startElementIdentifier = getMaximumElementIdentifier(mesh) + 1

        elementtemplate1 = mesh.createElementtemplate()
        elementtemplate1.setElementShapeType(Element.SHAPE_TYPE_CUBE)

        # LV base elements
        nedl = nidl + elementsCountAroundLV
        for e in range(10):
            eft1 = eft
            nids = None
            if e == 0:
                # 8-node atrial septum element 1
                nids = [ nidl +  0, nidl +  1, laNodeId[0][-1],   laNodeId[0][ 0], nidr        +  0, nidl + nowl +  1, raNodeId[0][ 1], laNodeId[1][ 0] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1], [])
                scaleEftNodeValueLabels(eft1, [ 5 ], [ Node.VALUE_LABEL_D_DS1 ], [ 1 ] )
                remapEftNodeValueLabel(eft1, [ 1, 3 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS3, [] ) ])
                remapEftNodeValueLabel(eft1, [ 5, 7 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 7, 8 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [1] ) ])
                scaleEftNodeValueLabels(eft1, [ 8 ], [ Node.VALUE_LABEL_D_DS3 ], [ 1 ] )
            elif e == 1:
                # 8-node atrial septum element 2
                nids = [ nidl +  1, nidl +  2, laNodeId[0][ 0],   laNodeId[0][ 1], nidl + nowl +  1, nidl + nowl +  2, laNodeId[1][ 0], raNodeId[0][-1] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1], [])
                remapEftNodeValueLabel(eft1, [ 4 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS1, [1] ), ( Node.VALUE_LABEL_D_DS3, [] ) ])
                scaleEftNodeValueLabels(eft1, [ 7 ], [ Node.VALUE_LABEL_D_DS1, Node.VALUE_LABEL_D_DS3 ], [ 1 ] )
                remapEftNodeValueLabel(eft1, [ 8 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS1, [1] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 8 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [1] ) ])
            elif e == 2:
                # 6-node crux element, multiple collapses
                nids = [ nidl +  2, lvOutletNodeId[0][0], laNodeId[0][ 1], lvOutletNodeId[1][0], nidl + nowl +  2, raNodeId[0][-1] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1], [])
                # remap parameters before collapsing nodes
                remapEftNodeValueLabel(eft1, [ 1 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [] ) ])
                remapEftNodeValueLabel(eft1, [ 2 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS2, [] ) ])
                tricubichermite.setEftLinearDerivative(eft1, [ 2, 4 ], Node.VALUE_LABEL_D_DS2, 2, 4, 1)
                tricubichermite.setEftLinearDerivative(eft1, [ 2, 6 ], Node.VALUE_LABEL_D_DS3, 2, 6, 1)
                # must set DS3 before DS1 to allow latter to equal former
                remapEftNodeValueLabel(eft1, [ 3 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS1, [1] ), ( Node.VALUE_LABEL_D_DS3, [] ) ])
                remapEftNodeValueLabel(eft1, [ 3 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS3, [] ) ])
                remapEftNodeValueLabel(eft1, [ 4 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS3, [1]) ])
                remapEftNodeValueLabel(eft1, [ 4, 8 ], Node.VALUE_LABEL_D_DS3, [])
                remapEftNodeValueLabel(eft1, [ 6, 8 ], Node.VALUE_LABEL_D_DS2, [])
                #remapEftNodeValueLabel(eft1, [ 5 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 5 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 6 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [1] ), ( Node.VALUE_LABEL_D_DS2, [] ) ])
                #remapEftNodeValueLabel(eft1, [ 6 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS2, [] ) ])
                # must set DS3 before DS1 to allow latter to equal former
                remapEftNodeValueLabel(eft1, [ 7 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS1, [1] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 7 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS3, []) ])
                remapEftNodeValueLabel(eft1, [ 8 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [1] ), ( Node.VALUE_LABEL_D_DS3, [1]) ])
                ln_map = [ 1, 2, 3, 4, 5, 4, 6, 4 ]
                remapEftLocalNodes(eft1, 6, ln_map)
            elif e == 3:
                # 6 node collapsed vs-ra shim element
                nids = [ lvOutletNodeId[1][0], lvOutletNodeId[1][1], nidl + nowl + 2, nidl + nowl + 3, raNodeId[0][-1], raNodeId[0][-2] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1], [])
                remapEftNodeValueLabel(eft1, [ 1, 2, 3, 4 ], Node.VALUE_LABEL_D_DS2, [ ])
                remapEftNodeValueLabel(eft1, [ 1 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                #remapEftNodeValueLabel(eft1, [ 1 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 2 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 3 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS3, [] ) ])
                #remapEftNodeValueLabel(eft1, [ 5 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS1, [1] ), ( Node.VALUE_LABEL_D_DS2, [1] ), ( Node.VALUE_LABEL_D_DS3, [] ) ])
                remapEftNodeValueLabel(eft1, [ 5 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS1, [1] ), ( Node.VALUE_LABEL_D_DS3, [] ) ])
                remapEftNodeValueLabel(eft1, [ 6 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS2, [1] ), ( Node.VALUE_LABEL_D_DS3, [] ) ])
                remapEftNodeValueLabel(eft1, [ 6 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [1] ), ( Node.VALUE_LABEL_D_DS2, [] ) ])
                scaleEftNodeValueLabels(eft1, [ 7, 8 ], [ Node.VALUE_LABEL_D_DS1, Node.VALUE_LABEL_D_DS3 ], [ 1 ])
                ln_map = [ 1, 2, 1, 2, 3, 4, 5, 6 ]
                remapEftLocalNodes(eft1, 6, ln_map)
            elif e <= 6:
                # 8-node ventricular septum elements
                n = e - 4
                nids = [ nidl + n + 2, nidl + n + 3, lvOutletNodeId[0][n], lvOutletNodeId[0][n + 1], nidl + nowl + n + 2, nidl + nowl + n + 3, lvOutletNodeId[1][n], lvOutletNodeId[1][n + 1] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1], [])
                tricubichermite.setEftLinearDerivative(eft1, [ 3, 7 ], Node.VALUE_LABEL_D_DS3, 3, 7, 1)
                tricubichermite.setEftLinearDerivative(eft1, [ 4, 8 ], Node.VALUE_LABEL_D_DS3, 4, 8, 1)
                # remap parameters before collapsing nodes
                if e == 4:
                    # the following will not be overridden by following remappings on the same node x value
                    remapEftNodeValueLabel(eft1, [ 1 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [] ) ])
                    #remapEftNodeValueLabel(eft1, [ 5 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                    remapEftNodeValueLabel(eft1, [ 5 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                    remapEftNodeValueLabel(eft1, [ 7 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [1] ), ( Node.VALUE_LABEL_D_DS2, [] ) ])
                #remapEftNodeValueLabel(eft1, [ 3, 4 ], Node.VALUE_LABEL_D_DS2, [ (Node.VALUE_LABEL_D_DS2, []), (Node.VALUE_LABEL_D_DS3, []) ])
                remapEftNodeValueLabel(eft1, [ 5, 6 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS2, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                #remapEftNodeValueLabel(eft1, [ 7, 8 ], Node.VALUE_LABEL_D_DS2, [ (Node.VALUE_LABEL_D_DS2, []), (Node.VALUE_LABEL_D_DS3, [1]) ])
            elif e == 7:
                # regular LV free wall - atria element
                nids = [ nedl -  3, nedl -  2, laNodeId[0][-4],   laNodeId[0][-3], nedl + nowl -  3, nedl + nowl -  2, laNodeId[1][-4], laNodeId[1][-3] ]
            elif e == 8:
                # regular LV free wall - atria element
                nids = [ nedl -  2, nedl -  1, laNodeId[0][-3],   laNodeId[0][-2], nedl + nowl -  2, nedl + nowl -  1, laNodeId[1][-3], laNodeId[1][-2] ]
            elif e == 9:
                # regular LV free wall - atria element
                nids = [ nedl -  1, nidl +  0, laNodeId[0][-2],   laNodeId[0][-1], nedl + nowl -  1, nidl + nowl +  0, laNodeId[1][-2], laNodeId[1][-1] ]

            result = elementtemplate1.defineField(coordinates, -1, eft1)
            element = mesh.createElement(elementIdentifier, elementtemplate1)
            result2 = element.setNodesByIdentifier(eft1, nids)
            if eft1.getNumberOfLocalScaleFactors() == 1:
                result3 = element.setScaleFactors(eft1, [ -1.0 ])
            else:
                result3 = 1
            print('create element lv', elementIdentifier, result, result2, result3, nids)
            elementIdentifier += 1

        # RV base elements
        scalefactors5hanging = [ -1.0, 0.5, 0.25, 0.125, 0.75 ]

        for e in range(12):
            eft1 = eft
            nids = None
            if e == 0:
                # lv-rv junction
                nids = [ nidl + 0, nidr + 0, laNodeId[0][-1], raNodeId[0][ 1], nidl + nowl + 0, nidr + nowr + 0, laNodeId[1][-1], raNodeId[1][ 1] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1], [])
                remapEftNodeValueLabel(eft1, [ 1, 3 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS3, [] ) ])
                remapEftNodeValueLabel(eft1, [ 2, 4 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
            elif e == 1:
                # regular rv free wall element 1
                nids = [ nidr        + 0, nidr + 1, raNodeId[0][ 1], raNodeId[0][ 2], nidr + nowr + 0, nidr + nowr + 1, raNodeId[1][ 1], raNodeId[1][ 2] ]
            elif e == 2:
                # regular rv free wall element 2
                nids = [ nidr        + 1, nidr + 2, raNodeId[0][ 2], raNodeId[0][ 3], nidr + nowr + 1, nidr + nowr + 2, raNodeId[1][ 2], raNodeId[1][ 3] ]
            elif e == 3:
                # 8-node rv free wall element 3
                nids = [ nidr        + 2, nidr + 3, raNodeId[0][ 3], raNodeId[0][ 4], nidr + nowr + 2, nidr + nowr + 3, raNodeId[1][ 3], raNodeId[1][ 4] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                remapEftNodeValueLabel(eft1, [ 4, 8 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [] ) ])
            elif e == 4:
                # supraventricular crest outer 1
                nids = [ nidr        + 3, nidr + 4, raNodeId[0][ 4],      crest_nid1, nidr + nowr + 3, nidr + nowr + 4, raNodeId[1][ 4],      crest_nid2 ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1], [])
                remapEftNodeValueLabel(eft1, [ 3, 7 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 3, 7 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [] ) ])
                #remapEftNodeValueLabel(eft1, [ 3, 7 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                #remapEftNodeValueLabel(eft1, [ 3, 7 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS2, [] ) ])
            elif e == 5:
                # supraventricular crest outer 2, infundibulum
                # 1st of pair of elements with hanging nodes at xi1=0.5 on xi2 == 0 plane
                nids = [ nidr + 4, nidr + 5, crest_nid1, rvOutletNodeId[0][2], nidr + nowr + 4, nidr + nowr + 5, crest_nid2, rvOutletNodeId[1][2] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1, 102, 104, 108, 304], [])
                tricubichermite.setEftMidsideXi1HangingNode(eft1, 2, 1, 1, 2, [1, 2, 3, 4, 5])
                tricubichermite.setEftMidsideXi1HangingNode(eft1, 6, 5, 5, 6, [1, 2, 3, 4, 5])
                tricubichermite.setEftLinearDerivative(eft1, [ 4, 8 ], Node.VALUE_LABEL_D_DS3, 4, 8, 1)
                remapEftNodeValueLabel(eft1, [ 4, 8 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [1] ), ( Node.VALUE_LABEL_D_DS2, [] ) ])  # must do before following
                remapEftNodeValueLabel(eft1, [ 4, 8 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS2, [] ) ])
            elif e == 6:
                # infundibulum
                # 2nd of pair of elements with hanging nodes at xi1=0.5 on xi2 == 0 plane
                nids = [ nidr + 4, nidr + 5, rvOutletNodeId[0][2], rvOutletNodeId[0][3], nidr + nowr + 4, nidr + nowr + 5, rvOutletNodeId[1][2], rvOutletNodeId[1][3] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1, 102, 104, 108, 304], [])
                tricubichermite.setEftMidsideXi1HangingNode(eft1, 1, 2, 1, 2, [1, 2, 3, 4, 5])
                tricubichermite.setEftMidsideXi1HangingNode(eft1, 5, 6, 5, 6, [1, 2, 3, 4, 5])
                tricubichermite.setEftLinearDerivative(eft1, [ 3, 7 ], Node.VALUE_LABEL_D_DS3, 3, 7, 1)
                tricubichermite.setEftLinearDerivative(eft1, [ 4, 8 ], Node.VALUE_LABEL_D_DS3, 4, 8, 1)
                remapEftNodeValueLabel(eft1, [ 3, 7 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [1] ), ( Node.VALUE_LABEL_D_DS2, [] ) ])
            elif e == 7:
                # infundibulum
                nids = [ nidr        + 5, nidr + 6, rvOutletNodeId[0][3], rvOutletNodeId[0][4], nidr + nowr + 5, nidr + nowr + 6, rvOutletNodeId[1][3], rvOutletNodeId[1][4] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1], [])
                tricubichermite.setEftLinearDerivative(eft1, [ 3, 7 ], Node.VALUE_LABEL_D_DS3, 3, 7, 1)
                tricubichermite.setEftLinearDerivative(eft1, [ 4, 8 ], Node.VALUE_LABEL_D_DS3, 4, 8, 1)
                #remapEftNodeValueLabel(eft1, [ 1, 5 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [] ) ])
            elif e == 8:
                # 7-node collapsed sv crest inner 1, by RA-LV outlet junction
                nids = [ raNodeId[0][-3], nidl + nowl +  4, raNodeId[0][-2], nidl + nowl + 3, raNodeId[1][-3], lvOutletNodeId[1][2], lvOutletNodeId[1][1] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1], [])
                remapEftNodeValueLabel(eft1, [ 1, 5 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 1, 5 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [] ) ])
                remapEftNodeValueLabel(eft1, [ 2 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 2, 4 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 2 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS2, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 3 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 3 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [] ) ])
                remapEftNodeValueLabel(eft1, [ 4 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 4 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS2, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 6 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 6 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 6, 8 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS2, [] ) ])
                remapEftNodeValueLabel(eft1, [ 7, 8 ], Node.VALUE_LABEL_D_DS1, [])
                remapEftNodeValueLabel(eft1, [ 7 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [1] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 7 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 8 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [1] ) ])
                ln_map = [ 1, 2, 3, 4, 5, 6, 7, 7 ]
                remapEftLocalNodes(eft1, 7, ln_map)
            elif e == 9:
                # 6-node wedge sv crest inner 2
                nids = [ raNodeId[0][-3], crest_nid1, nidl + nowl +  4, raNodeId[1][-3], crest_nid2, lvOutletNodeId[1][2] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1], [])
                remapEftNodeValueLabel(eft1, [ 1, 3, 5, 7 ], Node.VALUE_LABEL_D_DS2, [])
                remapEftNodeValueLabel(eft1, [ 1, 5 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 3, 7 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 4 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 4 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 4 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS2, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 8 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 8 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 8 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS2, [] ) ])
                ln_map = [ 1, 2, 1, 3, 4, 5, 4, 6 ]
                remapEftLocalNodes(eft1, 6, ln_map)
            elif e == 10:
                # 8-node wedge sv crest inner 3
                nids = [ crest_nid1, rvOutletNodeId[0][2], nidl + nowl +  4, rvOutletNodeId[0][1], crest_nid2, rvOutletNodeId[1][2], lvOutletNodeId[1][2], rvOutletNodeId[1][1] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1], [])
                tricubichermite.setEftLinearDerivative(eft1, [ 2, 6 ], Node.VALUE_LABEL_D_DS3, 2, 6, 1)
                tricubichermite.setEftLinearDerivative(eft1, [ 4, 8 ], Node.VALUE_LABEL_D_DS3, 4, 8, 1)
                remapEftNodeValueLabel(eft1, [ 2, 4, 6, 8 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [1] ) ])  # must do before following
                remapEftNodeValueLabel(eft1, [ 2, 4, 6, 8 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS2, [] ) ])
                remapEftNodeValueLabel(eft1, [ 3 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [] ) ])
                remapEftNodeValueLabel(eft1, [ 3 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS2, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 3 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS2, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 7 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS3, [] ) ])
                remapEftNodeValueLabel(eft1, [ 7 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 7 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS2, [] ) ])
            elif e == 11:
                # 8-node sv crest inner 4 by rv outlet
                nids = [ nidl + nowl +  4, rvOutletNodeId[0][1], nidl + nowl +  5, rvOutletNodeId[0][0], lvOutletNodeId[1][2], rvOutletNodeId[1][1], lvOutletNodeId[1][3], rvOutletNodeId[1][0] ]
                eft1 = tricubichermite.createEftNoCrossDerivatives()
                setEftScaleFactorIds(eft1, [1], [])
                tricubichermite.setEftLinearDerivative(eft1, [ 2, 6 ], Node.VALUE_LABEL_D_DS3, 2, 6, 1)
                tricubichermite.setEftLinearDerivative(eft1, [ 4, 8 ], Node.VALUE_LABEL_D_DS3, 4, 8, 1)
                remapEftNodeValueLabel(eft1, [ 1 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS2, [] ) ])
                remapEftNodeValueLabel(eft1, [ 3 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D2_DS1DS2, [] ) ])  # temporary, to swap with D_DS2
                remapEftNodeValueLabel(eft1, [ 1, 3 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [] ) ])
                remapEftNodeValueLabel(eft1, [ 1, 3 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS2, [] ), ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 2, 4 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [1] ) ])  # must do before following
                remapEftNodeValueLabel(eft1, [ 2, 4 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS2, [] ) ])
                remapEftNodeValueLabel(eft1, [ 3 ], Node.VALUE_LABEL_D2_DS1DS2, [ ( Node.VALUE_LABEL_D_DS2, [] ) ])  # swap from above
                remapEftNodeValueLabel(eft1, [ 5 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS1, [] ), ( Node.VALUE_LABEL_D_DS3, [] ) ])
                remapEftNodeValueLabel(eft1, [ 5 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [] ) ])
                remapEftNodeValueLabel(eft1, [ 5 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D_DS2, [] ) ])
                #remapEftNodeValueLabel(eft1, [ 6 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 6 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 6 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS2, [] ) ])
                remapEftNodeValueLabel(eft1, [ 7 ], Node.VALUE_LABEL_D_DS3, [ ( Node.VALUE_LABEL_D2_DS1DS2, [] ) ])  # temporary, to swap with D_DS2
                remapEftNodeValueLabel(eft1, [ 7 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS3, [] ) ])
                remapEftNodeValueLabel(eft1, [ 7 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [] ) ])
                remapEftNodeValueLabel(eft1, [ 7 ], Node.VALUE_LABEL_D2_DS1DS2, [ ( Node.VALUE_LABEL_D_DS2, [] ) ])
                remapEftNodeValueLabel(eft1, [ 8 ], Node.VALUE_LABEL_D_DS1, [ ( Node.VALUE_LABEL_D_DS3, [1] ) ])
                remapEftNodeValueLabel(eft1, [ 8 ], Node.VALUE_LABEL_D_DS2, [ ( Node.VALUE_LABEL_D_DS1, [1] ) ])

            result = elementtemplate1.defineField(coordinates, -1, eft1)
            element = mesh.createElement(elementIdentifier, elementtemplate1)
            result2 = element.setNodesByIdentifier(eft1, nids)
            if eft1.getNumberOfLocalScaleFactors() == 1:
                result3 = element.setScaleFactors(eft1, [ -1.0 ])
            elif eft1.getNumberOfLocalScaleFactors() == 5:
                result3 = element.setScaleFactors(eft1, scalefactors5hanging)
            else:
                result3 = 1
            print('create element rv', elementIdentifier, result, result2, result3, nids)
            elementIdentifier += 1

        fm.endChange()

    @staticmethod
    def refineMesh(meshrefinement, options):
        """
        Refine source mesh into separate region, with change of basis.
        :param meshrefinement: MeshRefinement, which knows source and target region.
        :param options: Dict containing options. See getDefaultOptions().
        """
        assert isinstance(meshrefinement, MeshRefinement)

        elementsCountAround = options['Number of elements around']
        elementsCountUp = options['Number of elements up']
        elementsCountThroughLVWall = options['Number of elements through LV wall']
        elementsCountAcrossSeptum = options['Number of elements across septum']
        elementsCountBelowSeptum = options['Number of elements below septum']

        refineElementsCountSurface = options['Refine number of elements surface']
        refineElementsCountThroughLVWall = options['Refine number of elements through LV wall']
        refineElementsCountThroughRVWall = options['Refine number of elements through RV wall']

        MeshType_3d_heartventricles2.refineMesh(meshrefinement, options)
        element = meshrefinement._sourceElementiterator.next()
        startBaseLvElementIdentifier = element.getIdentifier()
        startBaseRvElementIdentifier = startBaseLvElementIdentifier + 16
        startLvOutletElementIdentifier = startBaseRvElementIdentifier + 11
        limitLvOutletElementIdentifier = startLvOutletElementIdentifier + 6

        startHangingElementIdentifier = startBaseRvElementIdentifier + 4
        limitHangingElementIdentifier = startHangingElementIdentifier + 4

        while element.isValid():
            numberInXi1 = refineElementsCountSurface
            numberInXi2 = refineElementsCountSurface
            elementId = element.getIdentifier()
            if elementId < startBaseRvElementIdentifier:
                numberInXi3 = refineElementsCountThroughLVWall
            elif elementId < startLvOutletElementIdentifier:
                numberInXi3 = refineElementsCountThroughRVWall
                if (elementId >= startHangingElementIdentifier) and (elementId < limitHangingElementIdentifier):
                    numberInXi1 //= 2
            elif elementId < limitLvOutletElementIdentifier:
                numberInXi3 = 1
            meshrefinement.refineElementCubeStandard3d(element, numberInXi1, numberInXi2, numberInXi3)
            if elementId == (limitLvOutletElementIdentifier - 1):
                return  # finish on last so can continue in ventriclesbase
            element = meshrefinement._sourceElementiterator.next()

    @staticmethod
    def generateMesh(region, options):
        """
        Generate base or refined mesh.
        :param region: Zinc region to create mesh in. Must be empty.
        :param options: Dict containing options. See getDefaultOptions().
        """
        if not options['Refine']:
            MeshType_3d_heartventriclesbase2.generateBaseMesh(region, options)
            return
        baseRegion = region.createRegion()
        MeshType_3d_heartventriclesbase2.generateBaseMesh(baseRegion, options)
        meshrefinement = MeshRefinement(baseRegion, region)
        MeshType_3d_heartventriclesbase2.refineMesh(meshrefinement, options)
