from keras import backend as K
from keras.models import Model
from keras.engine.topology import Layer
from keras.layers import Input
from keras.layers.core import Dense, Lambda, Activation, Flatten
from keras.layers.convolutional import Conv2D
from keras.layers.merge import Concatenate, Add
from keras.layers.pooling import MaxPooling2D, AveragePooling2D
from keras.layers.normalization import BatchNormalization
from keras.regularizers import l2
from keras.callbacks import Callback, LearningRateScheduler, ModelCheckpoint, LambdaCallback, TensorBoard
from keras.optimizers import SGD
import os


class AttentionVGG:
    def __init__(self, att='att1', gmode='concat', compatibilityfunction='pc', datasetname="cifar100", height=32, width=32, channels=3, outputclasses=100, weight_decay=0.005, optimizer=SGD(lr=1, momentum=0.9, decay=0.0000001, nesterov=False), loss='categorical_crossentropy', metrics=['accuracy']):
        inp = Input(shape=(height, width, channels))
        regularizer = l2(weight_decay)

        x = Conv2D(64, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv1')(inp)
        x = Conv2D(64, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv2')(x)

        x = Conv2D(128, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv3')(x)
        x = Conv2D(128, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv4')(x)

        x = Conv2D(256, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv5')(x)
        x = Conv2D(256, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv6')(x)
        local1 = Conv2D(256, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv7')(x)  # batch*x*y*channel
        x = MaxPooling2D((2, 2), strides=(2, 2), name='pool1')(local1)

        x = Conv2D(512, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv8')(x)
        x = Conv2D(512, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv9')(x)
        local2 = Conv2D(512, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv10')(x)
        x = MaxPooling2D((2, 2), strides=(2, 2), name='pool2')(local2)

        x = Conv2D(512, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv11')(x)
        x = Conv2D(512, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv12')(x)
        local3 = Conv2D(512, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv13')(x)
        x = MaxPooling2D((2, 2), strides=(2, 2), name='pool3')(local3)

        x = Conv2D(512, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv14')(x)
        x = MaxPooling2D((2, 2), strides=(2, 2), name='pool4')(x)
        x = Conv2D(512, (3, 3), activation='relu', padding='same', kernel_regularizer=regularizer, name='conv15')(x)
        x = MaxPooling2D((2, 2), strides=(2, 2), name='pool5')(x)
        x = Flatten(name='pregflatten')(x)
        g = Dense(512, activation='relu', kernel_regularizer=regularizer, name='globalg')(x)  # batch*512

        l1 = Dense(512, kernel_regularizer=regularizer, name='l1connectordense')(local1)  # batch*x*y*512
        c1 = ParametrisedCompatibility(kernel_regularizer=regularizer, name='cpc1')([l1, g])  # batch*x*y
        if compatibilityfunction == 'dp':
            c1 = Lambda(lambda lam: K.squeeze(K.map_fn(lambda xy: K.dot(xy[0], xy[1]), elems=(lam[0], K.expand_dims(lam[1], -1)), dtype='float32'), 3), name='cdp1')([l1, g])  # batch*x*y
        flatc1 = Flatten(name='flatc1')(c1)  # batch*xy
        a1 = Activation('softmax', name='softmax1')(flatc1)  # batch*xy
        reshaped1 = Lambda(lambda la: K.map_fn(lambda lam: K.reshape(lam, [-1, 512]), elems=[la], dtype='float32'), name='reshape1')(l1)  # batch*xy*512.
        g1 = Lambda(lambda lam: K.squeeze(K.batch_dot(K.expand_dims(lam[0], 1), lam[1]), 1), name='g1')([a1, reshaped1])  # batch*512.

        height = height//2
        width = width//2
        l2 = local2
        c2 = ParametrisedCompatibility(kernel_regularizer=regularizer, name='cpc2')([l2, g])
        if compatibilityfunction == 'dp':
            c2 = Lambda(lambda lam: K.squeeze(K.map_fn(lambda xy: K.dot(xy[0], xy[1]), elems=(lam[0], K.expand_dims(lam[1], -1)), dtype='float32'), 3), name='cdp2')([l2, g])
        flatc2 = Flatten(name='flatc2')(c2)
        a2 = Activation('softmax', name='softmax2')(flatc2)
        reshaped2 = Lambda(lambda la: K.map_fn(lambda lam: K.reshape(lam, [-1, 512]), elems=[la], dtype='float32'), name='reshape2')(l2)
        g2 = Lambda(lambda lam: K.squeeze(K.batch_dot(K.expand_dims(lam[0], 1), lam[1]), 1), name='g2')([a2, reshaped2])

        height = height//2
        width = width//2
        l3 = local3
        c3 = ParametrisedCompatibility(kernel_regularizer=regularizer, name='cpc3')([l3, g])
        if compatibilityfunction == 'dp':
            c3 = Lambda(lambda lam: K.squeeze(K.map_fn(lambda xy: K.dot(xy[0], xy[1]), elems=(lam[0], K.expand_dims(lam[1], -1)), dtype='float32'), 3), name='cdp3')([l3, g])
        flatc3 = Flatten(name='flatc3')(c3)
        a3 = Activation('softmax', name='softmax3')(flatc3)
        reshaped3 = Lambda(lambda la: K.map_fn(lambda lam: K.reshape(lam, [-1, 512]), elems=[la], dtype='float32'), name='reshape3')(l3)
        g3 = Lambda(lambda lam: K.squeeze(K.batch_dot(K.expand_dims(lam[0], 1), lam[1]), 1), name='g3')([a3, reshaped3])

        out = ''
        if gmode == 'concat':
            glist = [g3]
            if att == 'att2':
                glist.append(g2)
            if att == 'att3':
                glist.append(g2)
                glist.append(g1)
            predictedG = g1
            if att != 'att1' and att != 'att':
                predictedG = Concatenate(axis=1, name='ConcatG')(glist)
            x = Dense(outputclasses, kernel_regularizer=regularizer, name=str(outputclasses)+'ConcatG')(predictedG)
            out = Activation("softmax", name='concatsoftmaxout')(x)
        else:
            gd3 = Dense(outputclasses, activation='softmax', name=str(outputclasses)+'indepsoftmaxg3')(g3)
            if att == 'att' or att == 'att1':
                out = gd3
            elif att == 'att2':
                gd2 = Dense(outputclasses, activation='softmax', kernel_regularizer=regularizer, name=str(outputclasses)+'indepsoftmaxg2')(g2)
                out = Add()([gd3, gd2], name='addg3g2')
                out = Lambda(lambda lam: lam/2, name='2average')(out)
            else:
                gd2 = Dense(outputclasses, activation='softmax', kernel_regularizer=regularizer, name=str(outputclasses)+'indepsoftmaxg2')(g2)
                gd1 = Dense(outputclasses, activation='softmax', kernel_regularizer=regularizer, name=str(outputclasses)+'indepsoftmaxg2')(g1)
                out = Add()([gd1, gd2, gd3], name='addg3g2g1')
                out = Lambda(lambda lam: lam/3, name='3average')(out)

        model = Model(inputs=inp, outputs=out)
        model.compile(optimizer=optimizer, loss=loss, metrics=metrics)
        name = ("(VGG-"+att+")-"+gmode+"-"+compatibilityfunction).replace('att)', 'att1)')
        print("Generated "+name)
        self.name = name
        self.model = model

    def StandardFit(self, X, Y, transfer=False):
        scheduler = LearningRateScaler(25, 0.5)
        startingepoch = 0
        pastepochs = list(map(int, [x.replace(".hdf5", "").replace(self.name+"-"+self.datasetname, "").replace(" ", "") for x in os.listdir("weights") if self.name+"-"+datasetname in x]))
        if pastepochs:
            if max(pastepochs) == 300:
                
                print("Found completely trained weights for "+self.name+"-"+self.datasetname)
                return
            self.model.load_weights("weights/"+self.name+"-"+self.datasetname+" "+str(max(pastepochs))+".hdf5")
            startingepoch = max(pastepochs)
        elif transfer:
            self.model.load_weights("weights/"+self.name+"-cifar100 300.hdf5", by_name=True)
            scheduler = LearningRateScheduler(transfer_schedule)
        tboardcb = TensorBoard(log_dir='./logs', histogram_freq=0, batch_size=3, write_graph=True, write_grads=False, write_images=False, embeddings_freq=0, embeddings_layer_names=None, embeddings_metadata=None)
        checkpoint = ModelCheckpoint("weights/"+self.name+"-"+self.datasetname+" {epoch}.hdf5", save_weights_only=True)
        epochprint = LambdaCallback(on_epoch_end=lambda epoch, logs: print("Passed epoch "+str(epoch)))
        callbackslist = [scheduler, checkpoint, epochprint, tboardcb]
        self.model.fit(X, Y, 128, 300, callbacks=callbackslist, initial_epoch=startingepoch,shuffle=False)
        return self.model

    def transfer_schedule(epoch):
            if epoch < 30:
                return 0.1
            if epoch < 60:
                return 0.2
            if epoch < 90:
                return 0.4
            if epoch < 120:
                return 0.2
            if epoch < 150:
                return 0.1
            if epoch < 180:
                return 0.05
            if epoch < 210:
                return 0.025
            if epoch < 240:
                return 0.0125
            if epoch < 270:
                return 0.00625
            return 0.003125


class ParametrisedCompatibility(Layer):

    def __init__(self, kernel_regularizer=None, **kwargs):
        super(ParametrisedCompatibility, self).__init__(**kwargs)
        self.regularizer = kernel_regularizer

    def build(self, input_shape):
        self.u = self.add_weight(name='u', shape=(512, 1), initializer='uniform', regularizer=self.regularizer, trainable=True)
        super(ParametrisedCompatibility, self).build(input_shape)

    def call(self, x):  # add l and g together with map_fn. Dot the sum with u.
        return K.dot(K.map_fn(lambda lam: lam[0]+lam[1], elems=(x), dtype='float32'), self.u)

    def compute_output_shape(self, input_shape):
        return (input_shape[0][0], input_shape[0][1], input_shape[0][2])


class LearningRateScaler(Callback):

    def __init__(self, epochs, multiplier):
        self.multiplier = multiplier
        self.epochs = epochs

    def on_epoch_begin(self, epoch, logs=None):
        if not hasattr(self.model.optimizer, 'lr'):
            raise ValueError('Optimizer must have a "lr" attribute.')
        oldrate = K.get_value(self.model.optimizer.lr)
        lr = oldrate*self.multiplier
        if epoch > 0 and epoch % self.epochs == 0:
            K.set_value(self.model.optimizer.lr, lr)
            print("Updated learning rate from "+str(oldrate)+" to "+str(lr)+" on epoch "+str(epoch))


if __name__ == "__main__":
    testmodel = AttentionVGG(att='att3', gmode='concat', compatibilityfunction='pc', datasetname="randomset", height=32, width=32, channels=3, outputclasses=10)
